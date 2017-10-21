
import logging
import socket
from threading import Thread
from time import sleep

logger = logging.getLogger("audio/"+__name__)


class PCMDecoder:
    """An asynchronous PCM decoder class for the default HFP codec audio.
    This doesn't do any decoding per-se, it simply passes the raw samples
    through to the sink.
    """

    def __init__(self):
        self._started = False
        self._worker = None

        self.on_close = None
        self.on_data_ready = None
        self.on_unhandled_error = None
        self.on_wav_params_ready = None

    def start(self, socket_or_fd, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        self._read_mtu = read_mtu

        # did we get socket or fd?
        self._socket = socket_or_fd
        if isinstance(socket_or_fd, int):
            logger.debug("PCMDecoder received fd, building socket...")
            self._socket = socket.socket(fileno=socket_or_fd)
        self._socket.setblocking(True)

        self._worker = Thread(
            target=self._do_decode,
            name="PCMDecoder",
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
        return 1
    
    @property
    def channel_mode(self):
        return "Mono"

    @property
    def sample_rate(self):
        return 8000

    @property
    def sample_size(self):
        return 16

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

        if unexpected_close and self.on_close:
            self.on_close()

    def _worker_proc(self):
        """Does the passing-through of PCM samples. Runs in an infinite
        loop until stopped.
        """

        # initialise
        if self.on_wav_params_ready:
            self.on_wav_params_ready()

        # loop until stopped
        while self._started:

            # read more PCM data
            try:
                data = self._socket.recv(self._read_mtu, socket.MSG_WAITALL)
            except Exception as e:
                # socket may have closed, up to stop() to be called
                logger.error("Socket read error - {}".format(e))
                data = b''
                sleep(0.25)    # don't consume 100% of CPU
            if len(data) == 0:
                continue
        
            #logger.debug("Got {} PCM bytes.".format(len(data)))

            # hand over data
            if self.on_data_ready:
                self.on_data_ready(
                    data=data)
