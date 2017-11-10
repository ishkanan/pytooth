
import logging

from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.pbap.managers import ProfileManager

logger = logging.getLogger(__name__)


class PhoneBookAccessProfile:
    """Top-level class for PBAP control via Bluez5 stack.
    """

    def __init__(self, system_bus, adapter_class, io_loop, *args, **kwargs):
        self._system_bus = system_bus

        # adapter
        adapter = adapter_class(
            system_bus=self._system_bus,
            io_loop=io_loop,
            *args,
            **kwargs)
        adapter.on_connected_changed = self._adapter_connected_changed
        adapter.on_properties_changed = self._adapter_properties_changed
        self._adapter = adapter

        # profile plumber
        pmgr = ProfileManager(
            system_bus=system_bus)
        pmgr.on_connected_changed = self._profile_connected_changed
        pmgr.on_unexpected_stop = self._profile_unexpected_stop
        self._profilemgr = pmgr

        # public events
        self.on_adapter_connected_changed = None
        self.on_device_connected_changed = None
        self.on_profile_status_changed = None

        # other
        self.io_loop = io_loop
        self._started = False

    def start(self):
        """Starts the profile. If already started, this does nothing.
        """
        if self._started:
            return

        self._adapter.start()
        self._profilemgr.start()
        self._started = True

    def stop(self):
        """Stops the profile. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._adapter.stop()
        self._profilemgr.stop()
        self._started = False

    @property
    def adapter_connected(self):
        """Returns if a suitable Bluetooth adapter is connected and in-use
        by this profile.
        """
        return self._adapter.connected

    def set_discoverable(self, enabled, timeout=None):
        """Set discoverable status.
        """
        self._adapter.set_discoverable(
            enabled=enabled,
            timeout=timeout)

    def set_pairable(self, enabled, timeout=None):
        """Set pairable status.
        """
        self._adapter.set_pairable(
            enabled=enabled,
            timeout=timeout)

    def _adapter_connected_changed(self, adapter, connected):
        """Adapter connected or disconnected.
        """
        if connected:
            logger.info("Adapter '{}' has connected.".format(
                adapter.address))

        else:
            logger.info("Adapter '{}' disconnected.".format(
                adapter.last_address))

        if self.on_adapter_connected_changed:
            self.on_adapter_connected_changed(adapter, connected)

    def _adapter_properties_changed(self, adapter, props):
        """Adapter properties changed.
        """
        logger.info("Adapter '{}' properties changed - {}".format(
            adapter.address,
            props))

    def _profile_connected_changed(self, device, connected):
        """Service-level connection has been established or ended with a
        remote device.
        """
        logger.debug("Device {} is now {}.".format(
            device, "connected" if connected else "disconnected"))

        if self.on_device_connected_changed:
            self.on_device_connected_changed(
                device=device,
                connected=connected)

    def _profile_unexpected_stop(self):
        """Profile was unregistered without our knowledge (something messing
        with Bluez5 perhaps).
        """
        logger.error("Profile unexpectedly unregistered.")

        if self.on_profile_status_changed:
            self.on_profile_status_changed(available=False)
