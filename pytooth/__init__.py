
import logging

from pydbus import SessionBus, SystemBus

from pytooth.constants import DBUS_ORG_NAME

logger = logging.getLogger("pytooth")


def init():
    """Performs important initial functions. Must be called before any other
    method in this library.
    """
    
    session_bus = SessionBus() # needed for org.bluez.obex
    system_bus = SystemBus()   # needed for everything else
    logger.debug("Acquiring DBus name '{}' on system bus...".format(
        DBUS_ORG_NAME))
    system_bus.request_name(name=DBUS_ORG_NAME)
    logger.debug("DBus name acquired.")
    return system_bus, session_bus
