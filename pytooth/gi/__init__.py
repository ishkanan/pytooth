"""Provides objects to control GTK functionality.
"""

from datetime import timedelta
import logging

from gi.repository import GLib

logger = logging.getLogger(__name__)


class GtkMainLoop:
    """Provides a GI main loop that encapsulates a Tornado IOLoop.
    """

    def __init__(self, io_loop):
        self.__deadline = timedelta(milliseconds=25)
        self.__gi_loop = GLib.MainLoop()
        self.__started = False
        
        self.io_loop = io_loop

    def start(self):
        """Starts the GI loop. If already started, this does nothing.
        """
        if self.__started:
            return

        self.__started = True
        GLib.timeout_add(50, self.__ioloop_run)
        self.__gi_loop.run()

    def stop(self):
        """Stops the GI loop. If already stopped, this does nothing.
        """
        if not self.__started:
            return

        self.__started = False
        self.__gi_loop.quit()

    def __ioloop_run(self):
        """Runs the Tornado IOLoop for a fixed amount of time, and cancels the
        GLib timeout if we have stopped.
        """
        self.io_loop.add_timeout(
            deadline=self.__deadline,
            callback=self.io_loop.stop)
        self.io_loop.start()
        return self.__started

