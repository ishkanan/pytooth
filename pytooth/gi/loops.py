"""Provides GTK IO loops.
"""
import logging

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from tornado.ioloop import IOLoop

logger = logging.getLogger(__name__)


class GtkMainLoop:
    """Encapsulates a GTK main loop that can dispatch asyncio events.
    """

    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        self.__gi_loop = GLib.MainLoop()
        self.__asyncio_loop = IOLoop.current()
        self.__started = False

    def start(self):
        """Starts the loop. If already started, this does nothing.
        """
        if self.__started:
            return

        self.__started = True
        GLib.timeout_add(25, self.__asyncio_pump)
        self.__gi_loop.run()

    def stop(self):
        """Stops the loop. If already stopped, this does nothing.
        """
        if not self.__started:
            return

        self.__started = False
        self.__gi_loop.quit()

    def __asyncio_pump(self):
        if not self.__started:
            return False

        self.__asyncio_loop.add_callback(self.__asyncio_loop.stop)
        self.__asyncio_loop.start()
        return True
