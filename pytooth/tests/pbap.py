"""Defines a test application for PBAP."""

import logging

from tornado.ioloop import IOLoop

from pytooth.adapters import OpenPairableAdapter
from pytooth.pbap import PhoneBookAccessProfile

logger = logging.getLogger(__name__)


class TestApplication:
    """Test application for the PBAP profile. Most of the logic of this code is
    suitable for use in a real-world application. The timer calling the
    `connect` method would most likely be substituted with a user action.
    """

    def __init__(self, session_bus, system_bus, config):
        # profile setup
        pbap = PhoneBookAccessProfile(
            session_bus=session_bus,
            system_bus=system_bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.current())
        pbap.on_adapter_connected_changed = self._adapter_connected_changed
        pbap.on_device_connected_changed = self._device_connected_changed
        pbap.on_profile_status_changed = self._profile_status_changed
        pbap.on_client_transfer_complete = self._client_transfer_complete
        pbap.on_client_transfer_error = self._client_transfer_error
        self.pbap = pbap

    def start(self):
        # let's go
        self.pbap.start()

        # this would probably be replaced with a user action
        IOLoop.current().call_later(
            delay=5,
            callback=self._connect_and_transfer)

    def stop(self):
        # cleanup
        if self.pbap.adapter_connected:
            self.pbap.set_discoverable(enabled=False)
            self.pbap.set_pairable(enabled=False)
        self.pbap.stop()

    def _connect_and_transfer(self):
        """Dummy function to connect and kick off a transfer.
        """
        try:
            client = self.pbap.connect(
                destination="ac:37:43:79:11:29")
        except Exception:
            logger.exception("Death during connect.")
            IOLoop.current().call_later(
                delay=5,
                callback=self._connect_and_transfer)
            return

        logger.debug("Selecting phonebook...")
        client.select("int", "pb")
        logger.debug("Selected phonebook.")
        logger.debug("Downloading entries from phonebook...")
        client.get_all()

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
        logger.info("PBAP profile is {}avaiable.".format("" if available else "not "))

    def _client_transfer_complete(self, client, data):
        """Fired when a transfer has completed successfully.
        """
        logger.debug("Transfer from '{}' has completed - # bytes={}".format(
            client.destination, len(data)))
        self.pbap.disconnect(destination=client.destination)

    def _client_transfer_error(self, client):
        """Fired when a transfer fails due to an error. Bluez5 does not provide
        error details.
        """
        logger.debug("Transfer from '{}' encountered an error.".format(
            client.destination))
        self.pbap.disconnect(destination=client.destination)
