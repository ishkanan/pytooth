
import logging

from pytooth.a2dp.constants import A2DP_SINK_UUID, MP3_CAPABILITIES, \
                                    MP3_CODEC, MP3_CONFIGURATION
from pytooth.bluez5.dbus import MediaEndpoint
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

        # DBus
        self._media = None
        self._media_endpoint = None
        self._media_endpoint_ctxt = None

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
        self._unregister_media()
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

    def _register_media(self, adapter):
        # build endpoint and register on DBus
        logger.debug("Building media endpoint...")
        self._media_endpoint = MediaEndpoint(
            system_bus=self._system_bus,
            configuration=MP3_CONFIGURATION)
        logger.debug("Registering media endpoint on DBus...")
        self._media_endpoint_ctxt = self._system_bus.register_object(
            path="/endpoints/a2dp",
            object=self._media_endpoint)

        # get Media proxy and register endpoint with bluez
        logger.debug("Fetching Media proxy...")
        self._media = Bluez5Utils.get_media(
            bus=self._system_bus,
            adapter_path=adapter.path)
        logger.debug("Registering media endpoint on bluez...")
        self._media.RegisterEndpoint(
            "/endpoints/a2dp",
            {
                "UUID" : A2DP_SINK_UUID,
                "Codec" : MP3_CODEC,
                "Capabilities" : MP3_CAPABILITIES
            })
        logger.debug("Registered and ready.")

    def _unregister_media(self):
        # unregister endpoint
        if self._media:
            logger.debug("Unregistering media endpoint...")
            self._media.UnregisterEndpoint("/endpoints/a2dp")
            self._media_endpoint_ctxt.unregister()
            self._media_endpoint = None
            self._media = None
            logger.debug("Unregistered media endpoint.")

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

