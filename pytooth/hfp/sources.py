
from datetime import timedelta
import logging
import select
from threading import Thread
from time import sleep

import pyaudio
from tornado.ioloop import IOLoop

logger = logging.getLogger(__name__)


class PortAudioSource:
    """Gets fed PCM samples from a PortAudio stream and writes the data to a
    socket pump.
    """

    def __init__(self, socket_pump, mtu, card_name):
        # attach to socket pump
        self._socket_pump = socket_pump
        self._socket_pump.on_fatal_error = self._fatal_pump_error

        # get card index of specified card
        self._recorder = pyaudio.PyAudio()
        try:
            self._device_index = -1
            for i in range(0, self._recorder.get_device_count()):
                device = self._recorder.get_device_info_by_index(i)
                if device["name"] == card_name:
                    self._device_index = i
                    break
            if self._device_index == -1:
                raise KeyError("Card not found.")
        except Exception:
            logger.exception("Card detection error.")
            raise
        finally:
            self._recorder.terminate()

        # other
        self.ioloop = IOLoop.current()
        self._mtu = mtu
        self._started = False

    def start(self):
        """Starts the source. If already started, this does nothing.
        """
        if self._started:
            return

        # prepare the PA stream
        self._recorder = pyaudio.PyAudio()
        self._stream = self._recorder.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=8000,
            frames_per_buffer=int(self._mtu / 2), # 2-byte samples/frames
            input=True,
            start=False,
            input_device_index=self._device_index,
            stream_callback=self._data_ready)
        self._started = True
        self._stream.start_stream()

    def stop(self):
        """Stops the source. If already stopped, this does nothing.
        """
        if not self._started:
            return

        # actual cleanup occurs in _stop_portaudio_callback() since we need to
        # gracefully clean PortAudio up by sending a termination flag

        self._started = False    

    def _stop_portaudio_callback(self):
        """Helper to do actual cleanup once stopped. Called indirectly from
        _data_ready() callback.
        """
        self._stream.stop_stream()
        self._stream.close()
        self._stream = None
        self._recorder.terminate()
        self._recorder = None

    def _data_ready(self, in_data, frame_count, time_info, status):
        """Called when PortAudio has samples for us. Called on a separate
        thread so watch yourself.
        """
        if not self._started:
            # not sure how to do this more reliably
            logger.debug("stop() has been called, safely stopping PortAudio.")
            self.ioloop.add_timeout(
                deadline=timedelta(milliseconds=250),
                callback=self._stop_data_ready)
            return (None, pyaudio.paComplete)

        # send data to the pump
        self._socket_pump.write(data=in_data)

        # more samples!
        return (None, pyaudio.paContinue)

    def _fatal_pump_error(self, error):
        """Called when a fatal socket pump error occurs. The pump automatically
        stops.
        """
        logger.critical("Fatal socket pump error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)
