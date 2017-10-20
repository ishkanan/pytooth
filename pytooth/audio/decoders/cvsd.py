
import ctypes as ct
import logging
import socket
from threading import Thread
from time import sleep

logger = logging.getLogger("audio/"+__name__)


class CVSDDecoder:
    """An asynchronous CVSD decoder class. Requires libliquid.
    """

    def __init__(self, libliquid_so_file):
        self._libliquid = ct.CDLL(libliquid_so_file)
        self._started = False
        self._worker = None

        self.on_close = None
        self.on_data_ready = None
        self.on_unhandled_error = None
        self.on_wav_params_ready = None

        self._cvsd = None

    def start(self, socket_or_fd, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        self._read_mtu = read_mtu

        # did we get socket or fd?
        self._socket = socket_or_fd
        if isinstance(socket_or_fd, int):
            logger.debug("CVSDDecoder received fd, building socket...")
            self._socket = socket.socket(fileno=socket_or_fd)
        self._socket.setblocking(True)

        self._worker = Thread(
            target=self._do_decode,
            name="CVSDDecoder",
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
        if self._started:
            return 1
        return None
    
    @property
    def channel_mode(self):
        if self._started:
            return "Mono"
        return None

    @property
    def sample_rate(self):
        if self._started:
            return 8000
        return None

    @property
    def sample_size(self):
        if self._started:
            return 1 # decoder will buffer 8 bits at a time
        return None

    def _do_decode(self):
        """Runs the decoder in a try/catch just in case something goes wrong.
        """

        unexpected_close = False

        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled decode error.")
            self._started = False
            self._socket.close()
            if self.on_unhandled_error:
                self.on_unhandled_error(error=e)
            unexpected_close = True
        finally:
            logger.debug("cvsd_destroy will be called.")
            self._libliquid.cvsd_destroy(ct.byref(self._cvsd))

        if unexpected_close and self.on_close:
            self.on_close()

    def _worker_proc(self):
        """Does the decoding of CVSD samples to WAV samples. Runs in an infinite
        loop until stopped.
        """

        # initialise
        logger.debug("CVSD C instance will be created...")
        self._cvsd = self._libliquid.cvsd_create(
            ct.c_uint(5),
            ct.c_float(1.5),
            ct.c_float(0.95))
        logger.debug("CVSD C instance was created.")
        decode_buf = ct.c_float * 8    # bulk decode buffer
        #if self.on_wav_params_ready:
        #    self.on_wav_params_ready()

        # loop until stopped
        while self._started:

            # read more CVSD data
            try:
                data = self._socket.recv(self._read_mtu, socket.MSG_WAITALL)
            except Exception as e:
                # socket may have closed, up to stop() to be called
                logger.error("Socket read error - {}".format(e))
                data = b''
                sleep(0.25)    # don't consume 100% of CPU
            if len(data) == 0:
                continue
        
            #logger.debug("Got {} bytes to decode.".format(len(data)))

            # decode loop
            for b in data:
                self._libliquid.cvsd_decode8(
                    self._cvsd,
                    ct.c_ubyte(b),
                    ct.byref(decode_buf))
                logger.debug("Encoded={}, Decoded={}".format(b, decode_buf.raw()))

            # hand over decoded data
            # if self.on_data_ready:
            #     self.on_data_ready(
            #         data=decode_buf.raw[0:total_written])
