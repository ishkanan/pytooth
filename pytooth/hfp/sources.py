
from datetime import timedelta
import logging
import select
from threading import Thread
from time import sleep

import pyaudio
from tornado.ioloop import IOLoop

from pytooth.other.buffers import ThreadSafeMemoryBuffer

logger = logging.getLogger(__name__)


class PortAudioSource:
    """Reads samples from an audio input device and writes them (in the correct
    format) an SCO socket.
    """

    def __init__(self, socket, write_mtu, card_name):
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
        self._buffer = ThreadSafeMemoryBuffer()
        self._socket_pump = Thread(
            target=self._socket_pump_proc,
            name="PASourceSocketPump",
            daemon=True
        )
        self._started = True
        self._socket_pump.start()
        self._stream.start_stream()

    def stop(self):
        """Stops the source. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._socket_pump.join()
        self._socket_pump = None
        self._socket = None
        self._buffer = None        

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

        # buffer the data for the pump
        self._buffer.append(in_data)

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

    def _socket_pump_proc(self):
        """Sends buffered data as fast as possible to the SCO socket. Note this
        isn't running in a Tornado-style loop since we have to operate as fast
        as possible, and that involves blocking operations.
        """

        # calculate sleep delay so we don't fall too far behind
        # => 8000 samples/src * 2-byte samples = 16000 bytes/sec
        # => 16000 bytes / MTU = X transmissions/sec
        # => 1000 msec / X = Y msec/transmission
        delay = int(1000 / (16000 / self._write_mtu))

        logger.debug("SCO socket source pump has started, delay = {}".format(
            delay))

        # 1) fetch data to send
        # 2) send data with retry
        # 3) repeat until apocalypse
        while self._started:

            # fetch in MTU-sized chunks
            if self._buffer.length < self._write_mtu:
                logger.debug("Pump waiting for data to send.")
                sleep(delay) # CPU busy safety
                continue
            data = self._buffer.get(self._write_mtu)
            
            # try send data, aborting on socket error
            while self._started:
                try:
                    result = select.select([], [self._socket.fileno()], [], 0)
                    if len(result[1]) == 0:
                        # socket not ready for a write, so wait
                        logger.debug("Pump waiting for socket to be writeable.")
                        sleep(delay) # CPU busy safety
                        continue
                    self._socket.sendall(data)
                    logger.debug("Pump sent data to socket.")
                    sleep(delay) # temp CPU busy safety
                    break
                except Exception as e:
                    logger.error("Error sending PCM data to SCO socket - {}".format(e))
                    sleep(delay) # CPU busy safety
                    break

        logger.debug("SCO socket source pump has gracefully stopped.")
