
import logging
import socket

from tornado.iostream import IOStream

logger = logging.getLogger(__name__)


class StreamSink:

    def __init__(self, fd):
        self._fd = fd
        s = socket.socket(fileno=fd)


        self._stream = IOStream(
            socket=s)

        self._stream.read_until_close(
            streaming_callback=self._data_ready)

    def _data_ready(self, data):
        logger.debug("Read {} bytes from socket.".format(len(data)))

    def close(self):
        self._stream.close()
