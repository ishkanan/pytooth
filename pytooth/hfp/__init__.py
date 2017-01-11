
import logging

from pytooth.hfp.managers import ProfileManager
from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger("hfp")


class HandsFreeProfile:
    """Wraps up HFP profile control via Bluez5 stack.
    """

    def __init__(self, system_bus, adapter_class, io_loop, *args, **kwargs):
        self._system_bus = system_bus

        # adapter
        self._adapter = adapter_class(
            system_bus=self._system_bus,
            io_loop=io_loop,
            *args,
            **kwargs)
        self._adapter.on_connected_changed = self._adapter_connected_changed
        self._adapter.on_properties_changed = self._adapter_properties_changed

        # profile plumber
        self._profilemgr = ProfileManager(
            system_bus=system_bus)
        self._profilemgr.on_connect = self._profile_connect
        self._profilemgr.on_disconnect = self._profile_disconnect
        self._profilemgr.on_unexpected_stop = self._profile_unexpected_stop

        # public events
        self.on_adapter_connected_changed = None
        self.on_adapter_properties_changed = None

        # other
        self.io_loop = io_loop
        self._started = False

    def start(self):
        """Starts the profile. If already started, this does nothing.
        """
        if self._started:
            return

        self._adapter.start()
        self._started = True

    def stop(self):
        """Stops the profile. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._adapter.stop()
        self._profilemgr.stop()
        self._started = False

    def _adapter_connected_changed(self, adapter):
        """Adapter connected or disconnected.
        """
        if adapter.connected:
            logger.info("Adapter '{}' has connected.".format(adapter.address))
            
            # start profile now after org name has been registered on DBus
            self._profilemgr.start()
        else:
            logger.info("Adapter disconnected.")

        # pass up
        if self.on_adapter_connected_changed:
            self.on_adapter_connected_changed(adapter=adapter)

    def _adapter_properties_changed(self, adapter, props):
        """Adapter properties changed.
        """
        logger.info("Adapter '{}' properties changed - {}".format(
            adapter.address,
            props))

        if self.on_adapter_properties_changed:
            self.on_adapter_properties_changed(adapter=adapter, props=props)

    def _profile_connect(self, device, fd, fd_properties):
        """New service-level connection has been established.
        """
        logger.debug("Device connected.")

    def _profile_disconnect(self, device):
        """Device is disconnected from profile.
        """
        logger.debug("Device disconnected.")

    def _profile_unexpected_stop(self):
        """Profile was unregistered without our knowledge.
        """
        logger.debug("Profile unexpectedly unregistered. Attempting re-register"
            " in 15 seconds...")
        self.io_loop.call_later(
            delay=15,
            callback=self._profilemgr.start)

    def set_discoverable(self, enabled, timeout=None):
        """Toggles visibility of the BT subsystem to other searching BT devices.
        Timeout is in seconds, or pass None for no timeout.
        """
        self._adapter.set_discoverable(enabled, timeout)

    def set_pairable(self, enabled, timeout=None):
        """Makes the BT subsystem pairable with other BT devices. Timeout is
        in seconds, or pass None for no timeout.
        """
        self._adapter.set_pairable(enabled, timeout)