
import logging

import pyaudio

logger = logging.getLogger("audio/sources/"+__name__)


class PortAudioSource:
    """Reads samples from an audio input device and writes them (in the correct
    format) an SCO socket.

    Note: we are cheating here and hard-coding formats because there can only be
    one for HFP and this is not used by A2DP.
    """

    def __init__(self, encoder, socket_or_fd, write_mtu, card_name):
        # attach to encoder
        self._encoder = encoder
        self._encoder.on_data_ready = self._data_ready
        self._encoder.on_unhandled_error = self._unhandled_encoder_error
        
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
        self._socket_or_fd = socket_or_fd
        self._write_mtu = write_mtu
        self._started = False

    def start(self):
        """Starts the source. If already started, this does nothing.
        """
        if self._started:
            return

        # did we get socket or fd?
        self._socket = self._socket_or_fd
        if isinstance(self._socket_or_fd, int):
            logger.debug("PortAudioSource received fd, building socket...")
            self._socket = socket.socket(fileno=self._socket_or_fd)
        self._socket.setblocking(True)

        # setup the rest and start
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
        	logger.error("Error sending data to SCO socket - {}".format(e))

    def _unhandled_encoder_error(self, error):
        """Called when an unhandled encoder error occurs. The encoder is
        automatically stopped.
        """
        logger.critical("Unhandled encoder error - {}".format(error))
