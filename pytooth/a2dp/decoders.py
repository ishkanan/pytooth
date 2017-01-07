
import ctypes as ct
import logging
import socket
from threading import Thread
from time import sleep

logger = logging.getLogger(__name__)


class sbc_t(ct.Structure):
    _fields_ = [
        ("flags", ct.c_ulong),
        ("frequency", ct.c_uint8),
        ("blocks", ct.c_uint8),
        ("subbands", ct.c_uint8),
        ("mode", ct.c_uint8),
        ("allocation", ct.c_uint8),
        ("bitpool", ct.c_uint8),
        ("endian", ct.c_uint8),
        ("priv", ct.c_void_p),
        ("priv_alloc_base", ct.c_void_p)]

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
        0: 1,
        1: 2,
        2: 2,
        3: 2
    }

    CHANNEL_MODE = {
        0: "Mono",
        1: "DualChannel",
        2: "Stereo",
        3: "JointStereo"
    }

    SAMPLE_SIZES = {
        0: 4,
        1: 8,
        2: 12,
        3: 16
    }

    def __init__(self, libsbc_so_file):
        self._libsbc = ct.CDLL(libsbc_so_file)
        self._started = False
        self._worker = None

        self.on_data_ready = None
        self.on_unhandled_error = None
        self.on_wav_params_ready = None

        # contains header info
        self._sbc = None
        self._sbc_populated = False

    def start(self, fd, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        self._read_mtu = read_mtu
        self._sbc = sbc_t()
        self._sbc_populated = False
        self._socket = socket.socket(fileno=fd)
        self._worker = Thread(
            target=self._do_decode,
            name="SBCDecoder",
            daemon=True)
        self._started = True
        self._worker.start()

    def stop(self):
        """Stops the decoder. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._socket.close()
        self._worker.join()

    @property
    def channels(self):
        if self._started and self._sbc_populated:
            return SBCDecoder.CHANNELS.get(self._sbc.mode)
        return None
    
    @property
    def channel_mode(self):
        if self._started and self._sbc_populated:
            return SBCDecoder.CHANNEL_MODE.get(self._sbc.mode)
        return None

    @property
    def samplerate(self):
        if self._started and self._sbc_populated:
            return SBCDecoder.SAMPLE_RATES.get(self._sbc.frequency)
        return None

    @property
    def samplesize(self):
        if self._started and self._sbc_populated:
            return SBCDecoder.SAMPLE_SIZES.get(self._sbc.blocks)
        return None

    def _do_decode(self):
        # run the thread in a try/catch just in case something goes wrong
        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled decode error.")
            self._started = False
            self._socket.close()
            if self.on_unhandled_error:
                self.on_unhandled_error(error=e)
        finally:
            logger.debug("sbc_finish will be called.")
            self._libsbc.sbc_finish(ct.byref(self._sbc), 0)

    def _worker_proc(self):
        # create read buffer
        bufsize = self._read_mtu
        buf = ct.create_string_buffer(bufsize)
        
        self._libsbc.sbc_init(ct.byref(self._sbc), 0)

        # loop until stopped
        while self._started:
            logger.debug("self._started = {}".format(self._started))

            # read more RTP data
            try:
                data = self._socket.recv(bufsize)
                logger.debug("Got {} bytes to decode.".format(len(data)))
            except Exception as e:
                logger.error("Socket read error - {}".format(e))
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
            if not self._sbc_populated:
                self._populate_sbct(data=data)
                logger.debug("sbc: fr={},bl={},sb={},m=o{},al={},bp={}".format(
                    self._sbc.frequency,
                    self._sbc.blocks,
                    self._sbc.subbands,
                    self._sbc.mode,
                    self._sbc.allocation,
                    self._sbc.bitpool))
                if self.on_wav_params_ready:
                    self.on_wav_params_ready()
                decode_bufsize = \
                    int(bufsize / SBCDecoder.SBC_MIN_FRAME_LEN + 1) * \
                    self._libsbc.sbc_get_codesize(ct.byref(self._sbc))
                decode_buf = ct.create_string_buffer(decode_bufsize)

            # progress tracking
            buf_p = ct.cast(buf, ct.c_void_p)
            decbuf_p = ct.cast(decode_buf, ct.c_void_p)
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
                    ct.byref(written))

                if decoded <= 0:
                    logger.debug("SBC decoding error - decoded={}".format(
                        decoded))
                    break # make do with what we have

                logger.debug("Decoded {} bytes.".format(decoded))

                # update buffer pointers / counters
                buf_p.value += decoded
                to_decode.value -= decoded
                decbuf_p.value += written.value
                to_write.value -= written.value
                total_written += written.value
        
            # hand over decoded data
            logger.debug("Total decoded {} bytes.".format(total_written))
            if self.on_data_ready:
                self.on_data_ready(
                    data=decode_buf.raw[0:total_written])

    def _populate_sbct(self, data):
        """Returns a sbc_t instance based on provided RTP packet that contains
        SBC-encoded payload.
        """
        if data[0] != 0x9c:
            raise TypeError("Not SBC-encoded payload.")

        # refer to official A2DP specification
        self._sbc.flags = 0
        self._sbc.frequency = (data[1] & 0xc0) >> 6
        self._sbc.blocks = (data[1] & 0x30) >> 4
        self._sbc.subbands = data[1] & 0x01
        self._sbc.mode = (data[1] & 0x0c) >> 2
        self._sbc.allocation = (data[1] & 0x02) >> 1
        self._sbc.bitpool = data[2]
        self._sbc.endian = 0

        self._sbc_populated = True
