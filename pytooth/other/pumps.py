"""Provides various pump classes."""

from functools import partial
import logging
import select
import socket
from threading import Thread
from time import sleep

from tornado.ioloop import IOLoop

from pytooth.errors import InvalidOperationError
from pytooth.other.buffers import ThreadSafeMemoryBuffer

logger = logging.getLogger(__name__)


class RealTimeSocketPump:
    """Reads and writes to an open socket in a thread-safe manner as fast as
    allowed to by the instantiator. As such, this will drop data it tries to
    send if a send error occurs.
    """

    def __init__(self):
        self.ioloop = IOLoop.current()
        self._started = False

        # public events
        self.on_data_ready = None
        self.on_fatal_error = None

    def start(self, socket, read_mtu, write_mtu, nodata_wait_msecs):
        """Starts the pump. If already started, this does nothing.
        """
        if self._started:
            return

        # setup
        self._send_buffer = ThreadSafeMemoryBuffer()
        self._nodata_wait_msecs = nodata_wait_msecs
        self._read_mtu = read_mtu
        self._write_mtu = write_mtu
        self._socket = socket
        self._socket.setblocking(True)
        self._worker = Thread(
            target=self._do_pump,
            name="BiDirectionalSocketPump",
            daemon=True
        )
        self._started = True
        self._worker.start()

    def stop(self):
        """Stops the pump. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._worker.join()
        self._socket = None
        self._read_mtu = None
        self._write_mtu = None
        self._nodata_wait_msecs = None
        self._send_buffer = None

    def write(self, data):
        """Queues data to send to the socket. Raises InvalidOperationError
        if the pump is not started.
        """
        if not self._started:
            raise InvalidOperationError("Socket pump is not started.")

        self._send_buffer.append(data)

    def _do_pump(self):
        """Runs the pump in a try/catch just in case something goes wrong.
        """
        try:
            self._worker_proc()
        except Exception as e:
            logger.exception("Unhandled socket pump error.")
            self.ioloop.add_callback(self.stop)
            if self.on_fatal_error:
                self.ioloop.add_callback(partial(
                    self.on_fatal_error,
                    error=e))

    def _worker_proc(self):
        """Performs the reads/writes on the socket in a dedicated thread.
        """

        logger.debug("Socket pump worker thread has started.")

        # setup
        nodata_delay = self._nodata_wait_msecs / 1000
        ep = select.epoll()
        ep.register(self._socket, select.EPOLLIN | select.EPOLLOUT)
        fatal = False

        # 1) check if socket ready for read/write
        # 2) sleep if no read/write was available
        # 3) perform read if applicable
        # 4) perform write if applicable
        while self._started or fatal:

            # step 1
            can_read = False
            can_write = False
            try:
                result = ep.poll(0.0)
                can_read = (result[0][1] & select.EPOLLIN) == select.EPOLLIN
                can_write = (result[0][1] & select.EPOLLOUT) == select.EPOLLOUT
            except Exception as e:
                logger.error("EPOLL error in pump worker thread - {}".format(e))
                if self.on_fatal_error:
                    self.ioloop.add_callback(partial(
                        self.on_fatal_error,
                        error=e))
                fatal = True
                continue

            # step 2
            if not can_read and not can_write:
                sleep(nodata_delay)
                continue

            error = False

            # step 3
            if can_read:
                try:
                    data = self._socket.recv(
                        self._read_mtu,
                        socket.MSG_WAITALL)
                    if self.on_data_ready:
                        self.ioloop.add_callback(partial(
                            self.on_data_ready,
                            data=data))
                except Exception as e:
                    logger.error("Pump socket read error - {}".format(e))
                    fatal = True

            # step 4
            if can_write and self._send_buffer.length >= self._write_mtu:
                try:
                    self._socket.send(
                        self._send_buffer.get(self._write_mtu))
                except Exception as e:
                    logger.error("Pump socket write error - {}".format(e))
                    fatal = True
            
            if error:
                sleep(0.01) # CPU busy safety

        #ep.unregister(self._socket)
        ep.close()

        if fatal:
            logger.debug(
                "Socket pump worker thread has stopped due to a fatal error.")
        else:
            logger.debug(
                "Socket pump worker thread has gracefully stopped.")
