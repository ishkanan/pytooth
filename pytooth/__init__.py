
import logging

import dbus

from pytooth.constants import DBUS_ORG_NAME

logger = logging.getLogger("pytooth")


def init():
    """Performs important initial functions. Must be called before any other
    method in this library.
    """
    
    bus = dbus.SystemBus()
    logger.debug("Acquiring DBus name '{}'...".format(DBUS_ORG_NAME))
    bus.request_name(name=DBUS_ORG_NAME)
    logger.debug("DBus name acquired.")
    return bus
