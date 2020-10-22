"""Provides various buffer classes."""

import logging
from threading import Lock

logger = logging.getLogger(__name__)


class ThreadSafeMemoryBuffer:
    """A very simple thread-safe memory buffer that stores raw bytes.
    """
    def __init__(self):
        self._buffer = b''
        self._lock = Lock()

    @property
    def length(self):
        with self._lock:
            return len(self._buffer)

    def get(self, num_bytes):
        with self._lock:
            data = self._buffer[0:num_bytes]
            self._buffer = self._buffer[num_bytes:]
            return data

    def prepend(self, data):
        with self._lock:
            self._buffer = data + self._buffer

    def append(self, data):
        with self._lock:
            self._buffer += data
