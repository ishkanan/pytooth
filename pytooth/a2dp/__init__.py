
import logging

from pydbus import SystemBus

logger = logging.getLogger("a2dp")


class AdvancedAudioProfile:
    """Wraps up A2DP profile control via Bluez5 stack. Adapted from this Bluez4
    example:

    http://www.lightofdawn.org/wiki/wiki.cgi/BluezA2DP
    """

    def __init__(self, adapter_class, *args, **kwargs):
        system_bus = SystemBus()

        # create adapter
        self.__adapter = adapter_class(system_bus=system_bus, *args, **kwargs)
        self.__adapter.on_connected_changed = \
            self.__adapter_connected_changed
        self.__adapter.on_properties_changed = \
            self.__adapter_properties_changed

        # public events
        self.on_adapter_connected_changed = None
        self.on_adapter_properties_changed = None

        # other
        self.__started = False
        self.io_loop = kwargs["io_loop"]

    def start(self):
        """Starts the profile. If already started, this does nothing.
        """
        if self.__started:
            return

        self.__adapter.start()
        self.__started = True

    def stop(self):
        """Stops the profile. If already stopped, this does nothing.
        """
        if not self.__started:
            return

        self.__started = False
        self.__adapter.stop()

    def __adapter_connected_changed(self, adapter):
        """Adapter connected or disconnected.
        """
        if adapter.connected:
            logger.info("Adapter with address '{}' has connected.".format(
                adapter.address))
        else:
            logger.info("Adapter disconnected.")

        if self.on_adapter_connected_changed:
            self.on_adapter_connected_changed(adapter=adapter)

    def __adapter_properties_changed(self, adapter, props):
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
        self.__adapter.set_discoverable(enabled, timeout)

    def set_pairable(self, enabled, timeout=None):
        """Makes the BT subsystem pairable with other BT devices. Timeout is
        in seconds, or pass None for no timeout.
        """
        self.__adapter.set_pairable(enabled, timeout)

