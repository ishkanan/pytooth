
import logging
import socket

from tornado.iostream import IOStream

logger = logging.getLogger(__name__)


class PortAudioSink:

    def __init__(self, transport, io_loop):
        self.io_loop = io_loop
        self._socket = socket.socket(fileno=transport.fd)
        self._stream = IOStream(socket=self._socket)
        self._transport = transport
        self._file = open('/home/vagrant/test.sbc', 'wb')

        self._stream.read_until_close(
            streaming_callback=self._data_ready)

    def _data_ready(self, data):
        if len(data) <= 0:
            return

        # find SBC syncword of packet
        i = 13#data.index(b'\x9c')
        if i < 0:
            return

        # decode data[i:]
        #logger.debug("Found i at {}, writing {} bytes.".format(
        #    i, len(data) - i))
        self._file.write(data[i:])

    def close(self):
        self._stream.close()
        self._file.close()
