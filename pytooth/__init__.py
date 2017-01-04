
import logging

from pydbus import SystemBus

from pytooth.constants import DBUS_ORG_NAME

logger = logging.getLogger("pytooth")


def init():
    """Performs important initial functions. Must be called before any other
    method in this library.
    """
    def name_aquired():
        logger.debug("DBus name acquired.")
    
    def name_lost():
        logger.debug("DBus name lost.")
    
    bus = SystemBus()
    logger.debug("Acquiring DBus name '{}'...".format(DBUS_ORG_NAME))
    bus.own_name(
        name=DBUS_ORG_NAME,
        name_aquired=name_aquired,
        name_lost=name_lost)
    return bus
