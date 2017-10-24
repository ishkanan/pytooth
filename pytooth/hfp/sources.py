
import logging

import pyaudio

logger = logging.getLogger(__name__)


class PortAudioSource:
    """Reads samples from an audio input device and writes them (in the correct
    format) an SCO socket.
    """

    def __init__(self, encoder, socket, write_mtu, card_name):
        # attach to encoder
        self._encoder = encoder
        self._encoder.on_data_ready = self._data_ready
        self._encoder.on_fatal_error = self._fatal_encoder_error
        
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
        self._socket = socket
        self._write_mtu = write_mtu
        self._started = False

    def start(self):
        """Starts the source. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._socket.setblocking(True)
        self._recorder = pyaudio.PyAudio()
        self._stream = self._recorder.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=8000,
            input=True,
            input_device_index=self._device_index,
            frames_per_buffer=64)
        self._started = True
        self._encoder.start(
            stream=self._stream)

    def stop(self):
        """Stops the source. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._encoder.stop()
        self._socket.close()
        self._socket = None
        self._stream.stop_stream()
        self._stream.close()
        self._recorder.terminate()

    def _data_ready(self, data):
        """Called when PCM data is ready.
        """
        if not self._started:
            return

        # TODO: send in write_mtu chunks
        try:
        	self._socket.sendall(data)
        except Exception as e:
        	logger.error("Error sending PCM data to SCO socket - {}".format(e))

    def _fatal_encoder_error(self, error):
        """Called when a fatal encoder error occurs. The encoder automatically
        stops.
        """
        logger.critical("Fatal encoder error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)
