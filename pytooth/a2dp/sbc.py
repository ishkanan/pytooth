
import ctypes as ct
from functools import partial
import logging
import socket
from threading import Thread
from time import sleep

from tornado.ioloop import IOLoop

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


class SBCDecoder:
    """An asynchronous SBC decoder class. Requires libsbc. This is capable of
    stripping RTP headers (for A2DP and other profiles).
    """

    def __init__(self, libsbc_so_file):
        self.ioloop = IOLoop.current()
        self._libsbc = ct.CDLL(libsbc_so_file)
        self._started = False
        self._worker = None

        self.on_data_ready = None
        self.on_fatal_error = None
        self.on_pcm_format_ready = None

        # contains header info
        self._sbc = None
        self._sbc_populated = False

    def start(self, socket, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._read_mtu = read_mtu
        self._sbc = sbc_t()
        self._sbc_populated = False
        self._socket = socket
        self._socket.setblocking(True)
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
        self._socket = None
        self._read_mtu = None
        self._worker.join()

    @property
    def channels(self):
        if self._sbc_populated:
            return CHANNELS.get(self._sbc.mode)
        return None

    @property
    def channel_mode(self):
        if self._sbc_populated:
            return CHANNEL_MODE.get(self._sbc.mode)
        return None

    @property
    def sample_rate(self):
        if self._sbc_populated:
            return SAMPLE_RATES.get(self._sbc.frequency)
        return None

    @property
    def sample_size(self):
        if self._sbc_populated:
            return SAMPLE_SIZES.get(self._sbc.blocks)
        return None

    def _do_decode(self):
        """Runs the decoder in a try/catch just in case something goes wrong.
        """
        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled decode error.")
            self.ioloop.add_callback(self.stop)
            if self.on_fatal_error:
                self.ioloop.add_callback(partial(
                    self.on_fatal_error,
                    error=e))
        finally:
            logger.debug("SBC decoder stopped - cleaning up libsbc.")
            self._libsbc.sbc_finish(ct.byref(self._sbc), 0)

    def _worker_proc(self):
        """Does the decoding of SBC samples to PCM samples. Runs in an infinite
        loop until stopped. Note the data format seems to be Big Endian/MSB.
        """

        # initialise
        bufsize = self._read_mtu
        buf = ct.create_string_buffer(bufsize)
        self._libsbc.sbc_init(ct.byref(self._sbc), 0)
        prev_seq = 0
        to_decode = ct.c_size_t()  # optimisation
        to_write = ct.c_size_t()   # optimisation
        written = ct.c_size_t()    # optimisation

        # loop until stopped
        while self._started:

            # read more RTP data in non-blocking mode
            # note: RTP boundaries are MTU boundaries
            packet = b''
            try:
                packet = self._socket.recv(
                    self._read_mtu,
                    socket.MSG_WAITALL)
            except Exception as e:
                logger.error("Socket read error - {}".format(e))
            if len(packet) == 0:
                sleep(0.1)  # CPU busy safety
                continue

            # out-of-order packet?
            # note: we need to allow for 16-bit reset
            seq = packet[3] + (packet[2] << 8)
            if seq < prev_seq and prev_seq - seq <= 50:
                logger.debug("Skipping old packet - prev={}, seq={}".format(
                    prev_seq, seq))
                continue
            prev_seq = seq

            # strip RTP padding
            has_padding = bool((packet[0] & 0x04) >> 2)
            if has_padding:
                num_pad_bytes = packet[-1]
                logger.debug("Stripping {} RTP pad bytes off the end.".format(
                    num_pad_bytes))
                packet = packet[:-num_pad_bytes]

            # strip RTP header (12) and payload header (1)
            data = packet[13:]
            buf.value = data
            readlen = len(data)

            # create decode buffer if we haven't already
            if not self._sbc_populated:
                try:
                    self._populate_sbct(data=data)
                except Exception as e:
                    logger.error(e)
                    continue
                logger.debug("sbc: freq={},blks={},sbnds={},mode={},alloc={},bpool={},flags={},endi={}".format(
                    self._sbc.frequency,
                    self._sbc.blocks,
                    self._sbc.subbands,
                    self._sbc.mode,
                    self._sbc.allocation,
                    self._sbc.bitpool,
                    self._sbc.flags,
                    self._sbc.endian))
                if self.on_pcm_format_ready:
                    self.ioloop.add_callback(self.on_pcm_format_ready)
                decode_bufsize = \
                    int(bufsize / SBC_MIN_FRAME_LEN + 1) * \
                    self._libsbc.sbc_get_codesize(ct.byref(self._sbc))
                decode_buf = ct.create_string_buffer(decode_bufsize)

            # progress tracking
            buf_p = ct.cast(buf, ct.c_void_p)
            decbuf_p = ct.cast(decode_buf, ct.c_void_p)
            to_decode.value = readlen
            to_write.value = decode_bufsize

            # decode loop, process as many frames as possible
            total_decoded = 0
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
                    logger.debug("SBC decoding error - decoded={}".format(decoded))
                    break  # make do with what we have

                # update buffer pointers / counters
                buf_p.value += decoded
                to_decode.value -= decoded
                total_decoded += decoded
                decbuf_p.value += written.value
                to_write.value -= written.value
                total_written += written.value

            # hand over decoded data on the main thread
            if self.on_data_ready:
                self.ioloop.add_callback(partial(
                    self.on_data_ready,
                    data=decode_buf.raw[0:total_written]))

    def _populate_sbct(self, data):
        """Returns a sbc_t instance based on provided RTP packet that contains
        SBC-encoded payload.
        """
        if data[0] != 0x9c:
            raise Exception("Not SBC-encoded payload.")

        # refer to official A2DP specification
        self._sbc.frequency = (data[1] & 0xc0) >> 6
        self._sbc.blocks = (data[1] & 0x30) >> 4
        self._sbc.subbands = data[1] & 0x01
        self._sbc.mode = (data[1] & 0x0c) >> 2
        self._sbc.allocation = (data[1] & 0x02) >> 1
        self._sbc.bitpool = data[2]

        self._sbc_populated = True
