
import logging

from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger("a2dp")


class AdvancedAudioProfile:
    """Wraps up A2DP profile control via Bluez5 stack. Adapted from this Bluez4
    example:

    http://www.lightofdawn.org/wiki/wiki.cgi/BluezA2DP
    """

    def __init__(self, system_bus, adapter_class, *args, **kwargs):
        self._system_bus = system_bus

        # create adapter
        self._adapter = adapter_class(
            system_bus=self._system_bus,
            *args,
            **kwargs)
        self._adapter.on_connected_changed = \
            self._adapter_connected_changed
        self._adapter.on_properties_changed = \
            self._adapter_properties_changed

        # public events
        self.on_adapter_connected_changed = None
        self.on_adapter_properties_changed = None

        # other
        self._started = False
        self.io_loop = kwargs["io_loop"]

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
        try:
            self._unregister_media()
        except Exception:
            logger.exception("Failed to unregister endpoint.")
        self._started = False

    def _adapter_connected_changed(self, adapter):
        """Adapter connected or disconnected.
        """
        if adapter.connected:
            logger.info("Adapter '{}' has connected.".format(adapter.address))
            self._register_media(adapter=adapter)
        else:
            logger.info("Adapter disconnected.")
            self._unregister_media(adapter=adapter)

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
