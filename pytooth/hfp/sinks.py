
import logging
import math

import alsaaudio

logger = logging.getLogger(__name__)


class AlsaAudioSink:
    """Gets fed PCM samples from a socket pump and writes the data to an
    Alsa device.
    """

    def __init__(self, socket_pump, device_name):
        # attach to socket pump
        self._socket_pump = socket_pump
        self._socket_pump.on_data_ready = self._data_ready
        self._socket_pump.on_fatal_error = self._fatal_pump_error

        # events
        self.on_fatal_error = None

        # other
        self._device_name = device_name
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        # open the ALSA device
        # note: CVSD support only
        self._device = alsaaudio.PCM(
            type=alsaaudio.PCM_PLAYBACK,
            mode=alsaaudio.PCM_NORMAL,
            rate=8000,
            channels=1,
            format=alsaaudio.PCM_FORMAT_S16_LE,
            periodsize=16,
            device=self._device_name)
        self._frame_size = 2  # channels * sample size
        self._remainder = b''
        self._started = True

    def stop(self):
        """Stops the sink. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False

        # cleanup ALSA device
        if not self._device:
            self._device.close()
            self._device = None

    def _data_ready(self, data):
        """Called when PCM data is ready.
        """
        if not self._started:
            return

        if self._device is None:
            logger.debug("ALSA device not opened - ignoring {} bytes.".format(
                len(data)))
            return

        # data = self._remainder + data
        # periods = math.floor(len(data)/self._frame_size)
        # periods = min(periods, 16)
        # self._device.write(data[0:periods*self._frame_size])
        # self._remainder = data[periods*self._frame_size:]
        self._device.write(data)

    def _fatal_pump_error(self, error):
        """Called when a fatal socket pump error occurs. The pump automatically
        stops.
        """
        logger.error("Fatal socket pump error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)
