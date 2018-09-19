
from datetime import datetime, timedelta
import logging

import alsaaudio
from tornado.ioloop import IOLoop

from pytooth.other.buffers import ThreadSafeMemoryBuffer

logger = logging.getLogger(__name__)


class AlsaAudioSink:
    """Drives an A2DP decoder and writes the resulting PCM samples to an
    Alsa device.
    """

    def __init__(self, decoder, socket, read_mtu, device_name):
        # attach to decoder
        self._decoder = decoder
        self._decoder.on_data_ready = self._data_ready
        self._decoder.on_fatal_error = self._fatal_decoder_error
        self._decoder.on_pcm_format_ready = self._pcm_format_ready
        
        # events
        self.on_fatal_error = None

        # other
        self.ioloop = IOLoop.current()
        self._device_name = device_name
        self._socket = socket
        self._read_mtu = read_mtu
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        # device setup can only occur once we know the PCM format
        self._device = None
        self._pcm_format_set = False
        self._started = True
        self._decoder.start(
            socket=self._socket,
            read_mtu=self._read_mtu)

    def stop(self):
        """Stops the sink. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._socket.close() # do this first else decoder may lock
        self._decoder.stop()

        # cleanup ALSA device
        if not self._device:
            self._device.close()
            self._device = None
        
        self._socket = None

    def _data_ready(self, data):
        """Called when PCM data is ready.
        """
        if not self._started:
            return

        if not self._pcm_format_set:
            logger.debug("PCM format not set - ignoring {} bytes.".format(
                len(data)))
            return

        if self._device is None:
            logger.debug("ALSA device not opened - ignoring {} bytes.".format(
                len(data)))
            return

        self._device.write(data)

    def _fatal_decoder_error(self, error):
        """Called when a fatal decoder error occurs. The decoder automatically
        stops.
        """
        logger.critical("Fatal decoder error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)

    def _pcm_format_ready(self):
        """Called when PCM format has been determined.
        """
        if not self._started:
            return

        logger.debug("PCM format ready - Channels={}, Rate={}, BitsPerSample={}".format(
            self._decoder.channel_mode,
            self._decoder.sample_rate,
            self._decoder.sample_size))
        alsa_format = "PCM_FORMAT_S{}_LE".format(self._decoder.sample_size)
        logger.debug("ALSA format const = {}".format(alsa_format))

        # open the ALSA device
        self._device = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, device=self._device_name)
        self._device.setchannels(self._decoder.channels)
        self._device.setrate(self._decoder.sample_rate)
        self._device.setformat(getattr(alsaaudio, alsa_format))
        self._pcm_format_set = True
