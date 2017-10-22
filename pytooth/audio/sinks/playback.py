
from datetime import datetime
import logging
from socket import socket

import pyaudio

logger = logging.getLogger("audio/sinks/"+__name__)


class PortAudioSink:
    """Drives a generic decoder and writes the resulting WAV samples to a
    PortAudio stream.
    """

    def __init__(self, decoder, socket_or_fd, read_mtu, card_name, buffer_secs = 2):
        # attach to decoder
        self._decoder = decoder
        self._decoder.on_data_ready = self._data_ready
        self._decoder.on_unhandled_error = self._unhandled_decoder_error
        self._decoder.on_wav_params_ready = self._wav_params_ready
        
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

        # other
        self._buffering = False
        self._buffer_start = None
        self._buffer_secs = buffer_secs
        self._socket_or_fd = socket_or_fd
        self._read_mtu = read_mtu
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        # player stream setup can only occur once we know the WAV parameters
        self._buffer = b''
        self._buffering = True
        self._player = pyaudio.PyAudio()
        self._stream = None
        self._wav_header_set = False
        self._started = True
        self._decoder.start(
            socket_or_fd=self._socket_or_fd,
            read_mtu=self._read_mtu)

    def stop(self):
        """Stops the sink. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._decoder.stop()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._player.terminate()
        self._buffer = b''
        self._buffering = False
    
    def _data_ready(self, data):
        """Called when WAV data is ready.
        """
        if not self._started:
            return

        if not self._wav_header_set:
            logger.debug("WAV header not set - not buffering {} bytes.".format(
                len(data)))
            return

        # remember bytes to later submit to PortAudio
        self._buffer += data

    def _wav_params_ready(self):
        """Called when WAV header parameters have been determined.
        """
        if not self._started:
            return

        logger.debug("Channels={}, Rate={}, BitsPerSample={}".format(
            self._decoder.channel_mode,
            self._decoder.sample_rate,
            self._decoder.sample_size))
        
        # now we can open the stream
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
        self._wav_header_set = True

        # and we need to buffer desired amount
        self._buffering = True
        self._buffer_start = datetime.now()

    def _unhandled_decoder_error(self, error):
        """Called when an unhandled decoder error occurs. The decoder is
        automatically stopped.
        """
        logger.critical("Unhandled decoder error - {}".format(error))

    def _data_required(self, in_data, frame_count, time_info, status):
        """Called when PortAudio needs more samples.
        """

        # if we don't have enough data, we hand PA dummy data
        # until our buffering window is finished
        if self._buffering:
            if not self._buffer_start:
                self._buffer_start = datetime.now()
            self._buffering = (datetime.now() - self._buffer_start).total_seconds() < self._buffer_secs

        # decide what data to hand PA
        if self._buffering:
            #logger.debug("We are buffering, handing dummy data.")
            return (self._underrun_frame * frame_count, pyaudio.paContinue)
        else:
            req_byte_count = self._frame_size * frame_count
            if len(self._buffer) >= req_byte_count:
                # we have real data to give PA
                data = self._buffer[0:req_byte_count]
                self._buffer = self._buffer[req_byte_count:]
                return (data, pyaudio.paContinue)
            else:
                #logger.debug("We are underrun, handing dummy data and starting buffering.")

                # we've underrun, so start buffering again!
                self._buffering = True
                self._buffer_start = datetime.now()
                return (self._underrun_frame * frame_count, pyaudio.paContinue)
