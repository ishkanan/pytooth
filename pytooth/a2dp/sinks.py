
import logging
import struct
import wave

from pytooth.a2dp.decoders import SBCDecoder

logger = logging.getLogger(__name__)


class FileSBCSink:

    def __init__(self, transport, filename):
        # built-in SBC decoder
        self._decoder = SBCDecoder(
            libsbc_so_file="/usr/local/lib/libsbc.so.1.2.0")
        self._decoder.on_data_ready = self._data_ready
        self._decoder.on_unhandled_error = self._unhandled_decoder_error
        self._decoder.on_wav_params_ready = self._wav_params_ready
        
        # other
        self._filename = filename
        self._started = False
        self._transport = transport

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        self._file = wave.open(self._filename, 'wb')
        self._wav_header_set = False
        self._started = True
        self._decoder.start(
            fd=self._transport.fd,
            read_mtu=self._transport.read_mtu)

    def stop(self):
        """Stops the sink. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._decoder.stop()
        self._file.close()

    def _data_ready(self, data):
        """Called when WAV data is ready.
        """
        if not self._started:
            return

        if not self._wav_header_set:
            logger.debug("WAV header not set - not writing {} bytes.".format(
                len(data)))
            return

        # pack bytes according to WAV header
        n = int(self._decoder.channels * self._decoder.samplesize/8)
        for i in range(0, len(data), n):
            # 1, 2 or 4 bytes
            if n == 1:
                frame = struct.pack("=B", data[i])
            elif n == 2:
                frame = struct.pack("=H", (data[i+1] << 8) + data[i])
            elif n == 4:
                frame = struct.pack("=HH",
                    (data[i+1] << 8) + data[i],
                    (data[i+3] << 8) + data[i+2])
            self._file.writeframes(frame)

    def _wav_params_ready(self):
        """Called when WAV header parameters have been determined.
        """
        if not self._started:
            return

        logger.debug("Channels={}, Rate={}, BitsPerSample={}".format(
            self._decoder.channel_mode,
            self._decoder.samplerate,
            self._decoder.samplesize))
        self._file.setparams((
            self._decoder.channels,
            int(self._decoder.samplesize / 8),
            self._decoder.samplerate,
            0,
            "NONE",
            "not compressed"))
        self._wav_header_set = True

    def _unhandled_decoder_error(self, error):
        logger.critical("Unhandled decoder error - {}".format(error))
