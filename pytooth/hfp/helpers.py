
from collections import defaultdict
import logging
import socket

from tornado.gen import coroutine, Future
from tornado.iostream import IOStream

from pytooth.hfp.constants import HF_FEATURES

logger = logging.getLogger("hfp/"+__name__)


class SerialPortConnection:
    """Models a serial connection to a remote device over a Bluetooth RFCOMM
    link. Provides send and receive functionality (with proper parsing), and
    can track replies to certain requests.
    """

    def __init__(self, fd, async_reply_delay, io_loop):
        self._async_reply_delay = async_reply_delay
        self._io_loop = io_loop
        self._remainder = b''
        # <code>: [{} ->
        #   "future": <future>
        #   "handle": <timeout handle>]
        self._reply_q = defaultdict(list)
        self._socket = socket.socket(fileno=fd)
        
        self.on_close = None
        self.on_error = None
        self.on_message = None

        self._stream = IOStream(socket=self._socket)
        self._stream.set_close_callback(self._on_close)
        self._stream.read_until_close(
            streaming_callback=self._data_ready)

    def close(self):
        """Voluntarily closes the RFCOMM connection.
        """
        self._stream.close()

    def _async_timeout(self, code):
        """Called when an expected async reply doesn't arrive in the expected
        timeframe.
        """
        qentry = self._reply_q[code].pop()
        qentry["future"].set_exception(
            TimeoutError("Did not receive reply."))

    def _data_ready(self, data):
        """Parses data that has been received over the serial connection.
        """
        logger.debug("Received {} bytes from AG over SLC - {}".format(
            len(data), data))
        if len(self._remainder) > 0:
            data = self._remainder + data
            logger.debug("Appended left-over bytes - {}".format(
                self._remainder))
        
        while True:
            # all AG -> HF messages are <cr><lf> delimited
            try:
                msg, data = data.split(b'\x0d\x0a', 1)
            except ValueError:
                self._remainder = data
                return

            # decode to ASCII, logging but ignoring decode errors
            try:
                msg = msg.decode('ascii', errors='strict')
            except UnicodeDecodeError as e:
                logger.warning("ASCII decode error, going to ignore dodgy "
                    "characters - {}".format(e))
                msg = msg.decode('ascii', errors='ignore')

            try:
                if len(msg) > 0:
                    self._on_message(msg)
            except Exception:
                logger.exception("Message handler threw an unhandled "
                    "exception with data \"{}\"".format(msg))

            if data == b'':
                self._remainder = b''
                return

    def _on_close(self, *args):
        """The connection was closed by either side.
        """
        self._stream = None
        self._remainder = b''
        logger.info("Serial port connection to AG was closed.")

        if self.on_close:
            self.on_close()

    def _on_message(self, msg):
        """Invoked with a parsed message that we must now process.
        """

        if msg == "ERROR":
            # cleaner to report errors separately
            if self.on_error:
                self.on_error()

        elif msg == "OK":
            # generic response
            if self.on_message:
                self.on_message(code="OK", data=None)

        else:
            # strip leading "+" and split from first ":"
            # e.g. +BRSF: ...
            code, params = msg[1:].split(":", maxsplit=1)

            # find a handler function
            func_name = "_handle_{}".format(code.lower())
            try:
                handler = getattr(self, func_name)
            except AttributeError:
                logger.warning("No handler for code {}, ignoring...".format(
                    code))
                return

            # get a Future if async tracking
            try:
                qentry = self._reply_q[code].pop()
                self._io_loop.remove_timeout(qentry["handle"])
            except IndexError:
                qentry = None

            # execute handler (and deal with Future)
            try:
                ret = handler(params=params)
            except Exception as e:
                if qentry:
                    qentry["future"].set_exception(e)
                raise
            if qentry:
                qentry["future"].set_result(ret)
            else:
                if self.on_message:
                    self.on_message(code=code, data=ret)
                    
    def _handle_brsf(self, params):
        """Supported features of the AG.
        """
        params = int(params)

        return {
            "3WAY": (params & 0x0001) == 0x0001,
            "NREC": (params & 0x0002) == 0x0002,
            "VOICE_RECOGNITION": (params & 0x0004) == 0x0004,
            "INBAND": (params & 0x0008) == 0x0008,
            "PHONE_VTAG": (params & 0x0010) == 0x0010,
            "WIDE_BAND": (params & 0x0020) == 0x0020
        }

    def _handle_cind(self, params):
        """Indicators sent by the AG.
        """
        pass

    def send_message(self, message, async_reply_code=None):
        """Sends a message. If async is not None, this returns a Future that can
        be yielded. The Future will resolve when the supplied reply code is next
        received. The Future will error-out if no reply is received in the delay
        (seconds) given in the constructor.
        """

        try:
            logger.debug("Sending \"{}\" over SCL.".format(message))
            data = message+"\x0a"
            self._stream.write(data.encode("ascii"))
        except Exception as e:
            logger.exception("Error sending \"{}\" over SCL.".format(
                message))
            raise ConnectionError("Error sending \"{}\" over SCL.".format(
                message))
        
        # async tracking?
        if async_reply_code:
            queue = self._reply_q[async_reply_code]
            fut = Future()
            handle = self._io_loop.call_later(
                delay=self._async_reply_delay,
                callback=self._async_timeout,
                code=async_reply_code)
            queue.append({
                "future": fut,
                "handle": handle})
            return fut

        return None

class RemotePhone:
    """Acts as a proxy to a remote AG (Audio Gateway).
    """

    def __init__(self, connection, io_loop):
        # serial connection helper
        self._connection = connection
        connection.on_close = self._connection_close
        connection.on_error = self._connection_error
        connection.on_message = self._connection_message

        # public events
        self.on_handshake_complete = None

        # other
        self._ag_features = None
        self.io_loop = io_loop

        # kick-off handshake
        self.io_loop.add_callback(self._do_handshake)

    def _connection_close(self):
        """Called when serial connection is closed.
        """
        self._connection = None

    def _connection_error(self):
        """Called when AG reports that an error occurred.
        """
        pass

    def _connection_message(self, code, data):
        """Called when AG sends us a message.
        """
        logger.debug("Received message {}{}".format(
            code, " - "+data if data else ""))

    @coroutine
    def _do_handshake(self):
        """Performs a handshake with the AG.
        """
        try:

            # features
            self._ag_features = yield self._connection.send_message(
                message="AT+BRSF={}".format(HF_FEATURES),
                async_reply_code="BRSF")
            logger.debug("BRSF response = {}".format(self._ag_features))
            if not self._ag_features["WIDE_BAND"]:
                logger.info("Device does not support HQ audio.")
                if self._connection:
                    self._connection.close()
                return

            # indicators
            response = yield self._connection.send_message(
                message="AT+CIND=?",
                async_reply_code="CIND")
            logger.debug("CIND=? response = {}".format(response))
            
        except TimeoutError as e:
            logger.warning("HFP handshake error - {}".format(e))
            if self._connection:
                self._connection.close()
            return

        # handshake is complete
        logger.debug("HFP handshake is complete.")
        if self.on_handshake_complete:
            self.on_handshake_complete()
