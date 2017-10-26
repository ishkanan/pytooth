
from datetime import datetime, timedelta
import logging

from tornado.ioloop import IOLoop
import pyaudio

logger = logging.getLogger(__name__)


class PortAudioSink:
    """Drives an A2DP decoder and writes the resulting PCM samples to a
    PortAudio stream.
    """

    def __init__(self, decoder, socket, read_mtu, card_name, buffer_secs = 2):
        # attach to decoder
        self._decoder = decoder
        self._decoder.on_data_ready = self._data_ready
        self._decoder.on_fatal_error = self._fatal_decoder_error
        self._decoder.on_pcm_format_ready = self._pcm_format_ready
        
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
        self._buffering = False
        self._buffer_start = None
        self._buffer_secs = buffer_secs
        self.ioloop = IOLoop.current()
        self._socket = socket
        self._read_mtu = read_mtu
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        # player stream setup can only occur once we know the PCM format
        self._player = pyaudio.PyAudio()
        self._buffer = b''
        self._buffering = True
        self._stream = None
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

        # cleanup responsibility is in two parts:
        # 1) stop() cleans up if stream hasn't started
        # 2) _data_required() cleans up if stream has started
        if not self._stream:
            self._player.terminate()
            self._player = None
        
        self._buffer = b''
        self._buffering = False
        self._socket = None

    def _stop_data_ready(self):
        """Helper to clean up stream and player. Called indirectly from
        _data_ready() callback.
        """
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

        if not self._pcm_format_set:
            logger.debug("PCM format not set - not buffering {} bytes.".format(
                len(data)))
            return

        # remember bytes to later submit to PortAudio
        self._buffer += data

    def _data_required(self, in_data, frame_count, time_info, status):
        """Called when PortAudio needs more samples. Called on a separate
        thread so watch yourself.
        """
        if not self._started:
            # not sure how to do this more reliably
            logger.debug("stop() has been called, so cleaning up PortAudio safely.")
            self.ioloop.add_timeout(
                deadline=timedelta(milliseconds=250),
                callback=self._stop_data_ready)
            return (self._underrun_frame * frame_count, pyaudio.paComplete)

        # if we don't have enough data, we hand PA silence frames until our
        # buffering window is finished
        if self._buffering:
            if not self._buffer_start:
                self._buffer_start = datetime.now()
            self._buffering = (datetime.now() - self._buffer_start).total_seconds() < self._buffer_secs

        # decide what data to hand PA
        if self._buffering:
            #logger.debug("Buffering - returning silence frames.")
            return (self._underrun_frame * frame_count, pyaudio.paContinue)
        else:
            req_byte_count = self._frame_size * frame_count
            if len(self._buffer) >= req_byte_count:
                # we have real data to give PA
                data = self._buffer[0:req_byte_count]
                self._buffer = self._buffer[req_byte_count:]
                return (data, pyaudio.paContinue)
            else:
                logger.debug("Underrun -started buffering.")

                # we've underrun, so start buffering again!
                self._buffering = True
                self._buffer_start = datetime.now()
                return (self._underrun_frame * frame_count, pyaudio.paContinue)

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
        
        # prepare the PA stream
        fmt = self._player.get_format_from_width(
            int(self._decoder.sample_size/8))
        logger.debug("Format = {}".format(fmt))
        self._frame_size = self._decoder.channels * int(self._decoder.sample_size/8)
        self._underrun_frame = bytes(self._frame_size)
        self._stream = self._player.open(
            format=fmt,
            channels=self._decoder.channels,
            rate=self._decoder.sample_rate,
            output=True,
            output_device_index=self._device_index,
            stream_callback=self._data_required)
        self._pcm_format_set = True

        # and we need to buffer desired amount
        self._buffering = True
        self._buffer_start = datetime.now()

        # and finally start
        self._stream.start_stream()
