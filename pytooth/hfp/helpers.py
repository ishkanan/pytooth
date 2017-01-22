
import ast
from collections import defaultdict
import logging
import socket

from tornado.gen import Future
from tornado.iostream import IOStream

logger = logging.getLogger("hfp/"+__name__)


class SerialPortConnection:
    """Models a serial connection to a remote device over a Bluetooth RFCOMM
    link. Provides send and receive functionality (with proper parsing), and
    can track replies to certain requests.
    """

    CHLD_MAP ={
        0: "ReleaseAllHeldOrUDUB",
        1: "ReleaseAllActive,AcceptOther",
        2: "HoldAllActive,AcceptOther",
        3: "AddCallToConference",
        4: "JoinCalls,HangUp"
    }

    CME_ERROR_MAP = {
        0: "AG failure",
        1: "No connection to phone",
        3: "Operation not allowed",
        4: "Operation not supported",
        5: "PH-SIM PIN required",
        10: "SIM not inserted",
        11: "SIM PIN required",
        12: "SIM PUK required",
        13: "SIM failure",
        14: "SIM busy",
        16: "Incorrect password",
        17: "SIM PIN2 required",
        18: "SIM PUK2 required",
        20: "Memory full",
        21: "Invalid index",
        23: "Memory failure",
        24: "Text string too long",
        25: "Invalid text string",
        26: "Dial string too long",
        27: "Invalid dial string",
        30: "No network service",
        31: "Network timeout",
        32: "Emergency calls only"
    }

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
        logger.debug("Received {} bytes from AG over SPC - {}".format(
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

        # error out any remaining futures
        for item in self._reply_q.values():
            item["future"].set_exception(
                ConnectionError("Connection was closed."))
        self._reply_q.clear()

        if self.on_close:
            self.on_close()

    def _on_message(self, msg):
        """Invoked with a parsed message that we must now process.
        """

        if msg == "ERROR":
            # cleaner to report errors separately
            if self.on_error:
                self.on_error(None)

        elif msg == "OK":
            # simple ACK
            # get a Future if async tracking
            try:
                qentry = self._reply_q["OK"].pop()
                self._io_loop.remove_timeout(qentry["handle"])
            except IndexError:
                qentry = None
            if qentry:
                qentry["future"].set_result("OK")
            else:
                if self.on_message:
                    self.on_message(code="OK", data=None)

        else:
            # strip leading "+" and split from first ":"
            # e.g. +BRSF: ...
            code, params = msg[1:].split(":", maxsplit=1)

            # shortcut to CME error reporting handler
            if code == "CME":
                if self.on_error:
                    self.on_error(self._handle_cme(params))
                return

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
                ret = handler(params=params.strip())
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

    def _handle_chld(self, params):
        """Info about how 3way/call wait is handled.
        """
        params = ast.literal_eval(params)
        return [SerialPortConnection.CHLD_MAP.get(f, f) for f in params]

    def _handle_ciev(self, params):
        """Single indicator update.
        """
        try:
            params = params.split(",")
            return {
                "name": self._indmap[int(params[0])-1],
                "value": params[1]}
        except IndexError:
            logger.debug("Unknown indicator, will ignore it.")

    def _handle_cind(self, params):
        """Indicators available by the AG. This class maps the indices to actual
        names to make it easier upstream.
        """
        # either initial indicator info...
        # ("call",(0,1)),("callsetup",(0-3)),("service",(0-1)),("signal",(0-5)),
        # ("roam",(0,1)),("battchg",(0-5)),("callheld",(0-2))
        if "(" in params:
            params = ast.literal_eval(params)
            self._indmap = dict([
                (i, name) for i, (name, _) in enumerate(params)])
            return [name for name, _ in params]

        # ...or initial indicator values
        # 0,0,1,4,0,3,0
        return dict([
            (self._indmap[i], val) for i, val in enumerate(params.split(","))])

    def _handle_cme(self, params):
        """Extended error code.
        """
        return SerialPortConnection.CME_ERROR_MAP.get(params, params)

    def send_message(self, message, async_reply_code=None):
        """Sends a message. If async is not None, this returns a Future that can
        be yielded. The Future will resolve when the supplied reply code is next
        received. The Future will error-out if no reply is received in the delay
        (seconds) given in the constructor.
        """

        try:
            logger.debug("Sending \"{}\" over SPC.".format(message))
            data = message+"\x0a"
            self._stream.write(data.encode("ascii"))
        except Exception as e:
            logger.exception("Error sending \"{}\" over SPC.".format(
                message))
            raise ConnectionError("Error sending \"{}\" over SPC.".format(
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
