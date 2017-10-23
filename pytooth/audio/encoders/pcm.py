
import logging
from threading import Thread
from time import sleep

import pyaudio

logger = logging.getLogger("audio/encoders/"+__name__)


class PCMEncoder:
    """An asynchronous PCM encoder class for the default HFP codec audio.
    This doesn't do any encoding per-se, it simply passes the raw samples
    (hard-coded to the correct format) through to the source.
    """

    def __init__(self):
        self._started = False
        self._worker = None

        self.on_close = None
        self.on_data_ready = None
        self.on_unhandled_error = None

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

        unexpected_close = False

        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled encode error.")
            self._started = False
            if self.on_unhandled_error:
                self.on_unhandled_error(error=e)
            unexpected_close = True

        if unexpected_close and self.on_close:
            self.on_close()

    def _worker_proc(self):
        """Does the passing-through of PCM samples. Runs in an infinite
        loop until stopped.
        """

        # loop until stopped
        while self._started:

            # read more PCM data
            try:
                data = self._stream.read(64)
            except Exception as e:
                # recorder may have terminated, up to stop() to be called
                logger.error("Recorder read error - {}".format(e))
                data = b''
                sleep(0.25)    # don't consume 100% of CPU
            if len(data) == 0:
                continue
        
            #logger.debug("Got {} PCM bytes.".format(len(data)))

            # hand over data
            if self.on_data_ready:
                self.on_data_ready(
                    data=data)
