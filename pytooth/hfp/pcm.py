
import logging
import select
import socket
from threading import Thread
from time import sleep

logger = logging.getLogger("hfp/"+__name__)


class PCMDecoder:
    """An asynchronous PCM decoder class for the default HFP codec audio.
    This doesn't do any decoding per-se, it simply passes the raw samples
    up the chain..
    """

    def __init__(self):
        self._started = False
        self._worker = None

        self.on_data_ready = None
        self.on_fatal_error = None
        self.on_pcm_format_ready = None

    def start(self, socket, read_mtu):
        """Starts the decoder. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._read_mtu = read_mtu
        self._socket = socket
        self._socket.setblocking(False)
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
        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled decode error.")
            self._started = False
            if self.on_fatal_error:
                self.on_fatal_error(error=e)

    def _worker_proc(self):
        """Does the passing-through of PCM samples. Runs in an infinite
        loop until stopped.
        """

        # initialise
        if self.on_pcm_format_ready:
            self.on_pcm_format_ready()

        # loop until stopped
        while self._started:

            # read more PCM data in non-blocking mode
            try:
                result = select.select([self._socket.fileno()], [], [], 0.25)
                data = b''
                if len(result[0]) == 1:
                    data = self._socket.recv(bufsize)#, socket.MSG_WAITALL)
            except Exception as e:
                logger.error("Socket read error - {}".format(e))
            if len(data) == 0:
                continue

            #logger.debug("Got {} PCM bytes.".format(len(data)))

            # hand over data
            if self.on_data_ready:
                self.on_data_ready(
                    data=data)

class PCMEncoder:
    """An asynchronous PCM encoder class for the default HFP codec audio.
    This doesn't do any encoding per-se, it simply passes the raw samples
    (hard-coded to the correct format) up the chain.
    """

    def __init__(self):
        self._started = False
        self._worker = None

        self.on_data_ready = None
        self.on_fatal_error = None
        self.on_pcm_format_ready = None

    def start(self, stream):
        """Starts the encoder. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._stream = stream
        self._worker = Thread(
            target=self._do_encode,
            name="PCMEncoder",
            daemon=True)
        self._started = True
        self._worker.start()

    def stop(self):
        """Stops the encoder. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
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

    def _do_encode(self):
        """Runs the encoder in a try/catch just in case something goes wrong.
        """
        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled encode error.")
            self._started = False
            if self.on_fatal_error:
                self.on_fatal_error(error=e)

    def _worker_proc(self):
        """Does the passing-through of PCM samples. Runs in an infinite
        loop until stopped.
        """

        # loop until stopped
        while self._started:

            # read more PCM data
            try:
                numframes = self._stream.get_read_available()
                data = b''
                if numframes > 0:
                    data = self._stream.read(numframes)
            except Exception as e:
                logger.error("Recorder read error - {}".format(e))
            if len(data) == 0:
                sleep(0.25)    # don't consume 100% of CPU
                continue

            #logger.debug("Got {} PCM bytes.".format(len(data)))

            # hand over data
            if self.on_data_ready:
                self.on_data_ready(
                    data=data)
