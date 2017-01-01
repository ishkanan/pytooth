
import logging

from pydbus import SystemBus

logger = logging.getLogger("pytooth")


def init():
    """Performs important initial functions. Must be called before any other
    method in this library.
    """
    def name_acquired(*args, **kwargs):
        logger.debug("Name acquired - args={}, kwargs={}".format(args, kwargs))
    
    def name_lost(*args, **kwargs):
        logger.debug("Name lost - args={}, kwargs={}".format(args, kwargs))
    
    bus = SystemBus()
    bus.own_name(
        name="local.pytooth",
        name_acquired=name_acquired,
        name_lost=name_lost)
    return bus
