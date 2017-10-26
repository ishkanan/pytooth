
import logging
from datetime import timedelta

import pyaudio
from tornado.ioloop import IOLoop

logger = logging.getLogger(__name__)


class PortAudioSource:
    """Reads samples from an audio input device and writes them (in the correct
    format) an SCO socket.
    """

    def __init__(self, encoder, socket, write_mtu, card_name):
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
        self._socket = socket
        self._write_mtu = write_mtu
        self._started = False

    def start(self):
        """Starts the source. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._socket.setblocking(False)
        self._recorder = pyaudio.PyAudio()
        self._stream = self._recorder.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=8000,
            frames_per_buffer=int(self._write_mtu / 2), # 2-byte samples/frames
            input=True,
            start=False,
            input_device_index=self._device_index,
            stream_callback=self._data_ready)
        self._buffer = b''
        self._started = True
        #self._encoder.start(
        #    stream=self._stream)
        self._stream.start_stream()

    def stop(self):
        """Stops the source. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        #self._encoder.stop()
        #self._socket.close()
        self._socket = None
        #self._stream.stop_stream()
        #self._stream.close()
        #self._recorder.terminate()

    def _stop_data_ready(self):
        """Helper to clean up stream and player. Called indirectly from
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
            logger.debug("stop() has been called, so cleaning up PortAudio safely.")
            self.ioloop.add_timeout(
                deadline=timedelta(milliseconds=250),
                callback=self._stop_data_ready)
            return (None, pyaudio.paComplete)

        # TODO: send in write_mtu chunks
        #self._buffer += in_data
        #logger.debug("{} new bytes, {} buffer bytes.".format(
        #    len(self._buffer), len(in_data)))
        #if len(self._buffer) >= self._write_mtu:
        #    data = self._buffer[0:self._write_mtu]
        #    self._buffer = self._buffer[self._write_mtu:]

        try:
            self._socket.send(in_data)
        except Exception as e:
            logger.error("Error sending PCM data to SCO socket - {}".format(e))
            #logger.debug("{} buffer bytes after send.".format(
            #    len(self._buffer)))

        # more samples!
        return (None, pyaudio.paContinue)

    def _fatal_encoder_error(self, error):
        """Called when a fatal encoder error occurs. The encoder automatically
        stops.
        """
        logger.critical("Fatal encoder error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)
