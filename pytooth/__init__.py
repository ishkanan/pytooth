
import logging

from pydbus import SystemBus

logger = logging.getLogger("pytooth")


def init():
    """Performs important initial functions. Must be called before any other
    method in this library.
    """
    def name_aquired(*args, **kwargs):
        logger.debug("Name acquired - args={}, kwargs={}".format(args, kwargs))
    
    def name_lost(*args, **kwargs):
        logger.debug("Name lost - args={}, kwargs={}".format(args, kwargs))
    
    bus = SystemBus()
    bus.own_name(
        name="dishpan.pytooth",
        name_aquired=name_aquired,
        name_lost=name_lost)
    return bus
