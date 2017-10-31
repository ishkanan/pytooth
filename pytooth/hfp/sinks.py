
from datetime import datetime, timedelta
import logging

import pyaudio
from tornado.ioloop import IOLoop

from pytooth.other.buffers import ThreadSafeMemoryBuffer

logger = logging.getLogger(__name__)


class PortAudioSink:
    """Gets fed PCM samples from a socket pump and writes the data to a
    PortAudio stream.
    """

    def __init__(self, socket_pump, card_name, buffer_msecs = 2000):
        # attach to socket pump
        self._socket_pump = socket_pump
        self._socket_pump.on_data_ready = self._data_ready
        self._socket_pump.on_fatal_error = self._fatal_pump_error
        
        # get card index of specified card
        self._player = pyaudio.PyAudio()
        try:
            self._device_index = -1
            for i in range(0, self._player.get_device_count()):
                device = self._player.get_device_info_by_index(i)
                if device["name"] == card_name:
                    self._device_index = i
                    break
            if self._device_index == -1:
                raise KeyError("Card not found.")
        except Exception:
            logger.exception("Card detection error.")
            raise
        finally:
            self._player.terminate()

        # events
        self.on_fatal_error = None

        # other
        self._buffer = None
        self._buffering = False
        self._buffer_end = None
        self._buffer_duration = timedelta(milliseconds=buffer_msecs)
        self.ioloop = IOLoop.current()
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._buffer = ThreadSafeMemoryBuffer()
        self._buffering = True
        self._buffer_end = datetime.now() + self._buffer_duration

        # prepare the PA stream
        self._player = pyaudio.PyAudio()
        self._frame_size = 1 * 2 # channels * bytes per sample
        self._underrun_frame = bytes(self._frame_size)
        self._stream = self._player.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=8000,
            output=True,
            start=False,
            output_device_index=self._device_index,
            stream_callback=self._data_required)
        self._started = True
        self._stream.start_stream()

    def stop(self):
        """Stops the sink. If already stopped, this does nothing.
        """
        if not self._started:
            return

        # actual cleanup occurs in _stop_portaudio_callback() since we need to
        # gracefully clean PortAudio up by sending a termination flag

        self._started = False
    
    def _stop_portaudio_callback(self):
        """Helper to do actual cleanup once stopped. Called indirectly from
        _data_required() callback.
        """
        self._buffer = None
        self._buffering = False
        self._buffer_end = None
        self._stream.stop_stream()
        self._stream.close()
        self._stream = None
        self._player.terminate()
        self._player = None

    def _data_ready(self, data):
        """Called when PCM data is ready.
        """
        if not self._started:
            return

        #logger.debug("Received {} bytes from socket pump.".format(len(data)))
        self._buffer.append(data)

    def _data_required(self, in_data, frame_count, time_info, status):
        """Called when PortAudio needs more samples. Called on a separate
        thread so watch yourself.
        """
        if not self._started:
            # not sure how to do this more reliably
            logger.debug("stop() has been called, safely stopping PortAudio.")
            self.ioloop.add_timeout(
                deadline=timedelta(milliseconds=250),
                callback=self._stop_portaudio_callback)
            return (self._underrun_frame * frame_count, pyaudio.paComplete)

        # if we don't have enough data, we hand PA silence frames until our
        # buffering window is finished
        # note: this guard stops us creating useless datetime objects if we
        #       are not buffering
        if self._buffering:
            self._buffering =  datetime.now() < self._buffer_end

        # decide what data to hand PA
        if self._buffering:
            #logger.debug("Buffering - returning silence frames.")
            return (self._underrun_frame * frame_count, pyaudio.paContinue)
        else:
            req_byte_count = self._frame_size * frame_count
            if self._buffer.length >= req_byte_count:
                # we have real data to give PA
                data = self._buffer.get(req_byte_count)
                return (data, pyaudio.paContinue)
            else:
                logger.debug("Underrun -started buffering.")

                # we've underrun, so start buffering again!
                self._buffering = True
                self._buffer_end = datetime.now() + self._buffer_duration
                return (self._underrun_frame * frame_count, pyaudio.paContinue)

    def _fatal_pump_error(self, error):
        """Called when a fatal socket pump error occurs. The pump automatically
        stops.
        """
        logger.critical("Fatal socket pump error - {}".format(error))
        self.stop()
        if self.on_fatal_error:
            self.on_fatal_error(error)
