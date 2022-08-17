
import logging

from tornado.gen import coroutine

from pytooth.errors import InvalidOperationError
from pytooth.hfp.constants import HF_BRSF_FEATURES
from pytooth.hfp.helpers import CallStateMachine

logger = logging.getLogger(__name__)


class RemotePhone:
    """Acts as a proxy to a remote AG (Audio Gateway). It handles the initial
    handshake between the AG and the HF, and exposes some state information and
    methods for performing actions on the AG.
    """

    def __init__(self, connection, io_loop):
        # serial connection helper
        self._connection = connection
        connection.on_close = self._connection_close
        connection.on_error = self._connection_error
        connection.on_message = self._connection_message

        # public events
        self.on_connected_changed = None
        self.on_event = None

        # other
        self._ag_features = None
        self._ag_multicall = None
        self._codec = None
        self._csm = None
        self._handshake_completed = False
        self.io_loop = io_loop
        self._started = False

    def start(self):
        """Kicks off handshake. Should only be called by HandsFreeProfile
        object.
        """
        if self._started:
            return

        self._csm = CallStateMachine()
        self.io_loop.add_callback(self._do_handshake)
        self._started = True

    @property
    def call_state(self):
        """Current state of calls present on the AG telephony device."""
        if not self._started:
            return None
        return self._csm.state

    @property
    def codec(self):
        """The SCO audio codec."""
        return self._codec

    @property
    def features(self):
        """Features supported by the AG."""
        return self._ag_features

    @property
    def multicall(self):
        """Multi-call handling capabilities of the AG."""
        return self._ag_multicall

    @property
    def peer(self):
        """Address of the remote device."""
        if self._connection is not None:
            return self._connection.peer
        return None

    def answer(self):
        """Request to answer an incoming call. This function raises an
        InvalidOperationError if not started or handshake is pending. Otherwise
        returns no value. State changes resulting from this function are
        available via the on_event() event.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if not self._handshake_completed:
            raise InvalidOperationError("Handshake not completed.")

        self._connection.send_message(message="ATA")

    def dial(self, number):
        """Initiates a call to the specified number. This function raises an
        InvalidOperationError if not started or handshake is pending. Otherwise
        returns no value. State changes resulting from this function are
        available via the on_event() event.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if not self._handshake_completed:
            raise InvalidOperationError("Handshake not completed.")

        self._connection.send_message(
            message="ATD{}".format(number))

    def hangup(self):
        """Request to hangup a connected call. This function raises an
        InvalidOperationError if not started or handshake is pending. Otherwise
        returns no value. State changes resulting from this function are
        available via the on_event() event.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if not self._handshake_completed:
            raise InvalidOperationError("Handshake not completed.")

        self._connection.send_message(message="AT+CHUP")

    def reject(self):
        """Request to reject an incoming call. This function raises an
        InvalidOperationError if not started or handshake is pending. Otherwise
        returns no value. State changes resulting from this function are
        available via the on_event() event.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if not self._handshake_completed:
            raise InvalidOperationError("Handshake not completed.")

        self._connection.send_message(message="AT+CHUP")

    def send_dtmf(self, dtmf):
        """Request to send DTMF to the network. This function raises an
        InvalidOperationError if not started or handshake is pending. Otherwise
        returns no value. State changes resulting from this function are
        available via the on_event() event.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if not self._handshake_completed:
            raise InvalidOperationError("Handshake not completed.")

        self._connection.send_message(
            message="AT+VTS={}".format(dtmf))

    def _connection_close(self):
        """Called when serial connection is closed.
        """
        self._connection = None
        if self.on_connected_changed:
            self.on_connected_changed(connected=False)

    def _connection_error(self, error):
        """Called when AG reports that an error occurred.
        """
        self._raise_event(name="error", error=error)

    def _connection_message(self, code, data):
        """Called when AG sends us a non-error message.
        """
        logger.debug("RFCOMM message received: {}{}".format(
            code, " - {}".format(data) if data else ""))

        # indicator update or initial values
        if code in ["CIEV", "CIND"] and isinstance(data, dict):
            if "battchg" in data:
                self._raise_event(name="battery", level=int(data["battchg"]))
            if "roam" in data:
                self._raise_event(name="roaming", roaming=data["roam"] == '1')
            if "service" in data:
                self._raise_event(name="service", service=data["service"] == '1')
            if "signal" in data:
                self._raise_event(name="signal", level=int(data["signal"]))

        # carrier
        if code == "COPS":
            self._raise_event(name="carrier", carrier=data["name"])

        # call state machine
        transitioned = self._csm.transition(name=code, data=data)
        if transitioned:
            self._raise_event(name="calls", state=self._csm.state)

    @coroutine
    def _do_handshake(self):
        """Performs a handshake with the AG according to the spec, plus a few
        other commands to set us up nicely.
        """
        logger.debug("HFP handshake is starting...")

        try:
            # features
            self._ag_features = yield self._send_and_wait(
                "AT+BRSF={}".format(HF_BRSF_FEATURES),
                "BRSF")
            logger.debug("AG feature set = {}".format(self._ag_features))

            # we could negotiate to mSBC if we support it later, but for now
            # only support CVSD/PCM
            self._codec = "CVSD"
            if self._ag_features["CODEC_NEG"]:
                yield self._send_and_wait("AT+BAC=1", "OK")
                # try:
                #     yield self._send_and_wait("AT+BAC=2", "OK")
                #     self._codec = "mSBC"
                # except TimeoutError:
                #     logger.debug("Failed to negotiate to mSBC codec.")

            # indicators
            yield self._send_and_wait("AT+CIND=?", "CIND")
            yield self._send_and_wait("AT+CIND?", "CIND")
            yield self._send_and_wait("AT+CMER=3,0,0,1", "OK")

            # specific to call wait/3-way
            if self._ag_features["3WAY"]:
                self._ag_multicall = yield self._send_and_wait(
                    "AT+CHLD=?", "CHLD")
                # call waiting alerts
                yield self._send_and_wait("AT+CCWA=1", "OK")

            # extended error handling
            yield self._send_and_wait("AT+CMEE=1", "OK")

            # CLI
            yield self._send_and_wait("AT+CLIP=1", "OK")

            # network operator format
            yield self._send_and_wait("AT+COPS=3,0", "OK")
            self._connection.send_message("AT+COPS?")
        except TimeoutError:
            logger.exception("HFP handshake error.")
            if self._connection:
                self._connection.close()
            return

        # handshake is complete
        self._handshake_completed = True
        logger.debug("HFP handshake is complete.")
        if self.on_connected_changed:
            self.on_connected_changed(connected=True)

    @coroutine
    def _send_and_wait(self, command, reply_code):
        """DRY helper function to send a command, wait for reply and log it.
        """
        response = yield self._connection.send_message(
            message=command,
            async_reply_code=reply_code)
        logger.debug("{} response = {}".format(command, response))
        return response

    def _raise_event(self, name, **kwargs):
        """Helper to raise an event and capture any exceptions that may bubble
        from the event processor.
        """
        if self.on_event:
            try:
                self.on_event(name=name, **kwargs)
            except Exception:
                logger.exception("Unhandled exception from event processor.")
