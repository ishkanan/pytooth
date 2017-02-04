"""Provides a streaming interface to the Sox utility.
"""

import logging

from tornado.iostream import IOStream
from tornado.process import Subprocess

from pytooth.errors import InvalidOperationError

logger = logging.getLogger("decoders/sox")


class SoxDecoder:
    """Decodes a stream of encoded data to Sox via stdin and receives the output
    on stdout.
    """

    def __init__(self, codec, out_channels, out_samplerate, out_samplesize):
        self._started = False

        # codec and WAV params
        self._codec = codec
        self._channels = out_channels
        self._sample_rate = out_samplerate
        self._sample_size = out_samplesize

        # events
        self.on_close = None
        self.on_data_ready = None
        self.on_unhandled_error = None
        self.on_wav_params_ready = None

    @property
    def codec(self):
        return self._codec
    
    @property
    def channels(self):
        return self._channels

    @property
    def channel_mode(self):
        return {
            1: "Mono",
            2: "Stereo"
        }.get(self._channels, "Unknown")
    
    @property
    def sample_rate(self):
        return self._sample_rate
    
    @property
    def sample_size(self):
        return self._sample_size

    def start(self, socket_or_fd, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        # process
        self._process = Subprocess(
            [
                "sox",
                "-t",
                self._codec,
                "-",
                "--bits",
                str(self._sample_size),
                "--channels",
                str(self._channels),
                "--rate",
                str(self._sample_rate),
                "-t",
                "wav",
                "-"
            ],
            stdin=Subprocess.STREAM,
            stdout=Subprocess.STREAM,
            stderr=Subprocess.STREAM)
        self._process.stdout.set_close_callback(self._on_close)
        self._process.stdout.read_until_close(
            streaming_callback=self._out_data_ready)
        self._process.stderr.read_until_close(
            streaming_callback=self._sox_error)

        # did we get socket or fd?
        sock = socket_or_fd
        if isinstance(socket_or_fd, int):
            logger.debug("SoxDecoder received fd, building socket...")
            sock = socket.socket(fileno=socket_or_fd)
        sock.setblocking(True)

        # input pump
        self._input = IOStream(socket=sock)
        self._input.read_until_close(self._in_data_ready)

        # start
        self._started = True

        # we know WAV params already
        if self.on_wav_params_ready:
            self.on_wav_params_ready()

    def stop(self):
        """Stops the decoder. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._process.proc.kill()
        self._process = None

    def _on_close(self, *args):
        """Called when the Sox process exits.
        """
        if not self._started:
            return

        self.stop()

        if self.on_close:
            self.on_close()

    def _in_data_ready(self, data):
        """Writes encoded data to the Sox input stream.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")

        self._process.stdin.write(data)

    def _out_data_ready(self, data):
        """Called when decoded data is ready.
        """
        if self.on_data_ready:
            self.on_data_ready(data=data)

    def _sox_error(self, data):
        """Called when Sox writes to stderr. This isn't necessarily fatal, so
        we don't close the process.
        """
        if self.on_unhandled_error:
            self.on_unhandled_error(error=data)
