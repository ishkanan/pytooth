
from collections import defaultdict
import logging
import socket

from tornado.gen import Future
from tornado.iostream import IOStream

logger = logging.getLogger("hfp/"+__name__)


class ServiceLevelConnection:
    """Models a SLC to a remote device over Bluetooth serial link.
    Provides send and receive functionality (with proper parsing), and can
    track replies to certain requests.
    """

    def __init__(self, fd, async_reply_delay, io_loop):
        self._async_reply_delay = async_reply_delay
        self._io_loop = io_loop
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
        logger.debug("Received {} bytes from SLC {} - {}".format(
            len(data), self, data))
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
                self._on_message(msg)
            except Exception:
                logger.exception("Message handler threw an unhandled "
                    "exception with data \"{}\"".format(msg))

            if data == b'':
                self._remainder = b''
                return

    def _on_close(self, *args):
        """The SLC has closed.
        """
        self._stream = None
        self._remainder = b''
        logger.info("Service-level connection to device was closed.")

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
                self.on_message(code="OK")

        else:
            # strip leading "+" and split from first ":"
            # e.g. +BRSF: ...
            code, params = msg[1:].split(":", 1)

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
        pass

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
            data = message+"\x0a"
            self._stream.write(data.encode("ascii"))
        except Exception as e:
            logger.exception("Error sending '{}' over SCL.".format(
                message))
            raise ConnectionError("Error sending '{}' over SCL.".format(
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
