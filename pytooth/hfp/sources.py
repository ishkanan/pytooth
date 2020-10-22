
from datetime import timedelta
import logging

import alsaaudio
from tornado.ioloop import IOLoop

logger = logging.getLogger(__name__)


class AlsaAudioSource:
    """Reads PCM samples from an Alsa device and writes the data to a
    socket pump.
    """

    def __init__(self, socket_pump, mtu, device_name):
        # attach to socket pump
        self._socket_pump = socket_pump
        self._socket_pump.on_fatal_error = self._fatal_pump_error

        # other
        self.ioloop = IOLoop.current()
        self._deadline = None
        self._device_name = device_name
        self._mtu = mtu
        self._started = False
        self.on_fatal_error = None

    def start(self):
        """Starts the source. If already started, this does nothing.
        """
        if self._started:
            return

        # open the Alsa device
        # note: CVSD support only
        self._device = alsaaudio.PCM(
            alsaaudio.PCM_CAPTURE,
            alsaaudio.PCM_NONBLOCK,
            device=self._device_name)
        self._device.setchannels(1)
        self._device.setrate(8000)
        self._device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        self._device.setperiodsize(2000)  # 0.25 seconds buffer
        self._deadline = timedelta(milliseconds=250)
        self._started = True
        self.ioloop.add_callback(self._read_data)

    def stop(self):
        """Stops the source. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False

        # cleanup ALSA device
        if not self._device:
            self._device.close()
            self._device = None

    def _read_data(self):
        """Read as much data as is available from the ALSA device. This is
        invoked at the same frequency as the buffer size specified in start().
        """
        if not self._started:
            return

        try:
            l, data = self._device.read()
            if l > 0:
                self._socket_pump.write(data)
        except Exception as e:
            logger.error("ALSA read error - {}".format(e))

        self.ioloop.add_timeout(
            deadline=self._deadline,
            callback=self._read_data)

    def _fatal_pump_error(self, error):
        """Called when a fatal socket pump error occurs. The pump automatically
        stops.
        """
        logger.error("Fatal socket pump error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)
