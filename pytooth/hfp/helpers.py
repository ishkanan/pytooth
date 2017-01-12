
import logging
import socket

from tornado.iostream import IOStream

logger = logging.getLogger("hfp/"+__name__)


class Connection:
    """Models a connection to a remote device over Bluetooth serial link.
    Provides send and receive functionality (with proper parsing), and can
    track replies to certain requests.
    """

    def __init__(self, fd):
        self._socket = socket.socket(fileno=fd)
        self._stream = IOStream(socket=self._socket)

        self.on_disconnected = None
        self.on_message_received = None

        self._stream.read_until_close(
            streaming_callback=self._data_ready)

    def _data_ready(self, data):
        # acr listener code here!!!
        pass

    def send_message(self, message):
        pass
