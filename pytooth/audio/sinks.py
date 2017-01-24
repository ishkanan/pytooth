
import logging
import pyaudio
import struct
import wave

logger = logging.getLogger("audio/"+__name__)


class FileSink:
    """Drives a generic decoder and writes the resulting WAV samples to a file.
    """

    def __init__(self, decoder, fd, read_mtu, filename):
        # attach to decoder
        self._decoder = decoder
        self._decoder.on_data_ready = self._data_ready
        self._decoder.on_unhandled_error = self._unhandled_decoder_error
        self._decoder.on_wav_params_ready = self._wav_params_ready
        
        # other
        self._fd = fd
        self._filename = filename
        self._read_mtu = read_mtu
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        self._file = wave.open(self._filename, 'wb')
        self._wav_header_set = False
        self._started = True
        self._decoder.start(
            fd=self._fd,
            read_mtu=self._read_mtu)

    def stop(self):
        """Stops the sink. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._decoder.stop()
        self._file.close()

    def _data_ready(self, data):
        """Called when WAV data is ready.
        """
        if not self._started:
            return

        if not self._wav_header_set:
            logger.debug("WAV header not set - not writing {} bytes.".format(
                len(data)))
            return

        # pack bytes according to WAV header
        n = int(self._decoder.channels * self._decoder.samplesize/8)
        for i in range(0, len(data), n):
            # 1, 2 or 4 bytes
            if n == 1:
                frame = struct.pack("=B", data[i])
            elif n == 2:
                frame = struct.pack("=H", (data[i+1] << 8) + data[i])
            elif n == 4:
                frame = struct.pack("=HH",
                    (data[i+1] << 8) + data[i],
                    (data[i+3] << 8) + data[i+2])
            self._file.writeframes(frame)

    def _wav_params_ready(self):
        """Called when WAV header parameters have been determined.
        """
        if not self._started:
            return

        logger.debug("Channels={}, Rate={}, BitsPerSample={}".format(
            self._decoder.channel_mode,
            self._decoder.samplerate,
            self._decoder.samplesize))
        self._file.setparams((
            self._decoder.channels,
            int(self._decoder.samplesize / 8),
            self._decoder.samplerate,
            0,
            "NONE",
            "not compressed"))
        self._wav_header_set = True

    def _unhandled_decoder_error(self, error):
        """Called when an unhandled decoder error occurs. The decoder is
        automatically stopped.
        """
        logger.critical("Unhandled decoder error - {}".format(error))

class PortAudioSink:
    """Drives a generic decoder and writes the resulting WAV samples to a
    PortAudio stream.
    """

    def __init__(self, decoder, fd, read_mtu, card_name):
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
        self._fd = fd
        self._read_mtu = read_mtu
        self._started = False

    def start(self):
        """Starts the sink. If already started, this does nothing.
        """
        if self._started:
            return

        # player stream setup can only occur once we know the WAV parameters
        self._buffer = b''
        self._player = pyaudio.PyAudio()
        self._stream = None
        self._wav_header_set = False
        self._started = True
        self._decoder.start(
            fd=self._fd,
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
            self._decoder.samplerate,
            self._decoder.samplesize))
        
        # now we can open the stream
        fmt = self._player.get_format_from_width(
            int(self._decoder.samplesize/8))
        logger.debug("Format = {}".format(fmt))
        self._frame_size = self._decoder.channels * int(self._decoder.samplesize/8)
        self._underrun_frame = bytes(self._frame_size)
        self._stream = self._player.open(
            format=fmt,
            channels=self._decoder.channels,
            rate=self._decoder.samplerate,
            output=True,
            output_device_index=self._device_index,
            stream_callback=self._data_required)

        self._wav_header_set = True

    def _unhandled_decoder_error(self, error):
        """Called when an unhandled decoder error occurs. The decoder is
        automatically stopped.
        """
        logger.critical("Unhandled decoder error - {}".format(error))

    def _data_required(self, in_data, frame_count, time_info, status):
        """Called when PortAudio needs more samples.
        """

        req_byte_count = self._frame_size * frame_count
        if len(self._buffer) >= req_byte_count:
            data = self._buffer[0:req_byte_count]
            self._buffer = self._buffer[req_byte_count:]
            #logger.debug("Giving decoded data - {}".format(len(data)))
            return (data, pyaudio.paContinue)
        else:
            #logger.debug("Giving underrun data.")
            return (self._underrun_frame * frame_count, pyaudio.paContinue)
