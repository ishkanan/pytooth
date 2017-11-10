"""Defines a test application for PBAP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.pbap import PhoneBookAccessProfile
from pytooth.adapters import OpenPairableAdapter

logger = logging.getLogger(__name__)


class TestApplication:
    """Test application for the PBAP profile. The logic of this code is suitable
    for use in a real-world application.
    """

    def __init__(self, bus, config):
        # profile setup
        pbap = PhoneBookAccessProfile(
            system_bus=bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.current())
        pbap.on_adapter_connected_changed = self._adapter_connected_changed
        pbap.on_device_connected_changed = self._device_connected_changed
        pbap.on_profile_status_changed = self._profile_status_changed
        self.pbap = pbap

    def start(self):
        # let's go
        self.pbap.start()

    def stop(self):
        # cleanup
        if self.pbap.adapter_connected:
            self.pbap.set_discoverable(enabled=False)
            self.pbap.set_pairable(enabled=False)
        self.pbap.stop()

    def _adapter_connected_changed(self, adapter, connected):
        logger.debug("Adapter {} is now {}.".format(
            adapter, "connected" if connected else "disconnected"))

        # be discoverable and pairable if adapter is connected
        # note: it is an error to call this if no adapter is avilable
        if connected:
            self.pbap.set_discoverable(enabled=True)
            self.pbap.set_pairable(enabled=True)

    def _device_connected_changed(self, device, connected):
        """Fired when a device connects but has not completed initial handshake
        with the protocol.
        """
        logger.info("Device {} has {}connected.".format(
            device, "" if connected else "not "))

    def _profile_status_changed(self, available):
        """Fired when the profile is enabled/disabled at the Bluez5 level. This
        really only occurs if a serious issue with the Bluetooth stack is
        encountered by the OS.
        """
        logger.info("PBAP profile is {}avaiable.".format(
            "" if avaiable else "not "))
