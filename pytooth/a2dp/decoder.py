
import ctypes as ct
import logging
import socket
from threading import Thread
from time import sleep

logger = logging.getLogger(__name__)


class SBCDecoder:
    """An asynchronous SBC decoder class. Requires libsbc.
    """

    SBC_MIN_FRAME_LEN = 11
    
    SAMPLE_RATES = {
        0: 16000,
        1: 32000,
        2: 44100,
        3: 48000
    }

    CHANNELS = {
        0: "Mono",
        1: "DualChannel",
        2: "Stereo",
        3: "JointStereo"
    }

    def __init__(self, libsbc_so_file):
        self._libsbc = ct.cdll.LoadLibrary(libsbc_so_file)
        help(self._libsbc.sbc_t)
        self._started = False
        self._worker = None

        self.on_data_ready = None

        # contains header info
        self._sbc = None

    def start(self, fd, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        self._read_mtu = read_mtu
        self._sbc = None
        self._socket = socket.socket(fileno=fd)
        self._worker = Thread(
            target=self._do_decode,
            name="SBCDecoder",
            daemon=True)
        self._worker.run()
        self._started = True

    def stop(self):
        """Stops the decoder. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._socket.close()
        self._worker.join()

    @property
    def samplerate(self):
        if self._started and self._sbc:
            return SBCDecoder.SAMPLE_RATES.get(self._sbc.frequency)
        return None

    @property
    def channels(self):
        if self._started and self._sbc:
            return SBCDecoder.CHANNELS.get(self._sbc.mode)
        return None

    def _do_decode(self):
        # just in case something goes wrong
        try:
            self._worker_proc()
        except Exception:
            logger.exception("Decode error.")
            self._started = False
            self._socket.close()

    def _worker_proc(self):
        # create read buffer
        bufsize = self._read_mtu
        buf = ct.create_string_buffer(bufsize)

        # loop until stopped
        while self._started:

            # read more RTP data
            try:
                data = self._socket.recv(bufsize)
            except socket.error:
                # socket may have closed, up to stop() to be called
                data = ""
            if len(data) <= 0:
                sleep(1)    # don't consume 100% of CPU
                continue

            # crudely strip RTP
            data = data[13:] # RTP header (12) + RTP payload (1)
            buf.value = data
            readlen = len(data)
            
            # create decode buffer if we haven't already
            if not self._sbc:
                self._sbc = self._sbct_from_data(data=data)
                logger.debug("sbc = {}".format(self._sbc))
                decode_bufsize = \
                    (bufsize / SBCDecoder.SBC_MIN_FRAME_LEN + 1) * \
                    self._libsbc.sbc_get_codesize(ct.byref(self._sbc)).value
                decode_buf = ct.create_string_buffer(decode_bufsize)

            # progress tracking
            buf_p = ct.cast(buf, ct.c_void_p)
            decbuf_p = ct.cast(decode_buf, c_void_p)
            to_decode = ct.c_size_t(readlen)
            to_write = ct.c_size_t(decode_bufsize)

            # decode loop
            written = ct.c_size_t()
            total_written = 0
            while to_decode.value > 0:
                written.value = 0

                decoded = self._libsbc.sbc_decode(
                    ct.byref(self._sbc),
                    buf_p,
                    to_decode,
                    decbuf_p,
                    to_write,
                    ct.byref(written)).value

                if decoded <= 0:
                    logger.debug("SBC decoding error: {}".format(decoded))
                    break # make do with what we have

                logger.debug("Decoded {} bytes.".format(decoded))
                raise NotImplementedError("Got this far!")

                # update buffer pointers / counters
                buf_p.value += decoded
                to_decode.value -= decoded
                decbuf_p.value += written.value
                to_write.value -= written.value
                total_written += written.value
        
            # hand over decoded data
            if self.on_data_ready:
                self.on_data_ready(
                    data=decode_buf.raw[0:total_written])

    def _sbct_from_rtp(self, data):
        """Returns a sbc_t instance based on provided RTP packet that contains
        SBC-encoded payload.
        """
        if data[13] != 0x9c:
            raise TypeError("Not SBC-encoded payload.")

        # refer to official A2DP specification
        sbc = self._libsbc.sbc_t()
        sbc.flags = 0
        sbc.frequency = (data[2] & 0xc0) >> 6
        sbc.blocks = (data[2] & 0x30) >> 4
        sbc.subbands = data[2] & 0x01
        sbc.mode = (data[2] & 0x0c) >> 2
        sbc.allocation = (data[2] & 0x02) >> 1
        sbc.bitpool = data[3]
        sbc.endian = 0
        return sbc
