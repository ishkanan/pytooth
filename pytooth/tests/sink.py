
import logging
import socket

from tornado.iostream import IOStream

logger = logging.getLogger(__name__)


class StreamSink:

    def __init__(self, transport, io_loop):
        self.io_loop = io_loop
        self._socket = socket.socket(fileno=transport.fd)
        self._stream = IOStream(socket=self._socket)
        self._transport = transport

        self._stream.read_until_close(
            streaming_callback=self._data_ready)

    def _data_ready(self, data):
        logger.debug("Got {} bytes of data from socket.".format(
            len(data)))

    def close(self):
        self._stream.close()
