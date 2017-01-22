
import logging

from tornado.gen import coroutine

from pytooth.hfp.constants import HF_FEATURES

logger = logging.getLogger("hfp/"+__name__)


class RemotePhone:
    """Acts as a proxy to a remote AG (Audio Gateway). This also handles the
    initial handshake between the AG and the HF.
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
        self._ag_multicall = None
        self.io_loop = io_loop

        # kick-off handshake
        self.io_loop.add_callback(self._do_handshake)

    def _connection_close(self):
        """Called when serial connection is closed.
        """
        self._connection = None

    def _connection_error(self, error):
        """Called when AG reports that an error occurred.
        """
        logger.warning("AG reported an error - {}".format(error))

    def _connection_message(self, code, data):
        """Called when AG sends us a message.
        """
        logger.debug("Got message {}{}".format(
            code, " - {}".format(data) if data else ""))

    @coroutine
    def _do_handshake(self):
        """Performs a handshake with the AG according to the spec, plus a few
        other commands to set us up nicely.
        """
        try:

            # features
            self._ag_features = yield self._send_and_wait(
                "AT+BRSF={}".format(HF_FEATURES), "BRSF")
            logger.debug("BRSF response = {}".format(self._ag_features))
            if not self._ag_features["WIDE_BAND"]:
                raise InvalidOperationError("Device does not support HQ audio.")

            # indicators
            yield self._send_and_wait("AT+CIND=?", "CIND")
            yield self._send_and_wait("AT+CIND?", "CIND")
            yield self._send_and_wait("AT+CMER=3,0,0,1", "OK")

            # specific to call wait/3-way
            if self._ag_features["3WAY"]:
                self._ag_multicall = yield self._send_and_wait(
                    "AT+CHLD=?", "CHLD")
                yield self._send_and_wait("AT+CCWA=1", "OK")
                
            # extended error handling
            yield self._send_and_wait("AT+CMEE=1", "OK")

            # CLI
            yield self._send_and_wait("AT+CLIP=1", "OK")

            # network operator format
            yield self._send_and_wait("AT+COPS=3,0", "OK")
            self._connection.send_message("AT+COPS?")

        except TimeoutError as e:
            logger.warning("HFP handshake error - {}".format(e))
            if self._connection:
                self._connection.close()
            return

        # handshake is complete
        logger.debug("HFP handshake is complete.")
        if self.on_handshake_complete:
            self.on_handshake_complete()

    @coroutine
    def _send_and_wait(self, command, reply_code):
        """DRY helper function to send a command, wait for reply and log it.
        """
        response = yield self._connection.send_message(
            message=command,
            async_reply_code=reply_code)
        logger.debug("{} response = {}".format(command, response))
        return response
