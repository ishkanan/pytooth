
import logging

from pytooth.a2dp.constants import A2DP_SINK_UUID, MP3_CAPABILITIES, \
                                    MP3_CODEC, MP3_CONFIGURATION
from pytooth.bluez5.dbus import Media, MediaEndpoint
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

        # subscribe to property changes
        system_bus.subscribe(
            iface=Bluez5Utils.PROPERTIES_INTERFACE,
            signal="PropertiesChanged",
            arg0=Bluez5Utils.MEDIA_INTERFACE,
            signal_fired=self._media_properties_changed)

        # public events
        self.on_adapter_connected_changed = None
        self.on_adapter_properties_changed = None
        self.on_media_release = None
        self.on_media_setup_error = None
        self.on_playback_state_changed = None

        # DBus
        self._media = None
        self._media_endpoint = None
        self._media_transport = None

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
    
    def _media_properties_changed(self, sender, object, iface, signal, params):
        """Fired by the system bus subscription when a Bluez5 object property
        changes. 
        e.g.
            object=/org/bluez/hci0/dev_BC_F5_AC_81_D0_9E
            iface=org.freedesktop.DBus.Properties
            signal=PropertiesChanged
            params=('org.bluez.Device1', {'Connected': True}, [])
        """
        if not self._started:
            return
        if params[0] != Bluez5Utils.MEDIA_INTERFACE:
            return
        
        logger.debug("SIGNAL: object={}, iface={}, signal={}, params={}".format(
            object, iface, signal, params))

    def _media_release(self):
        """Media release.
        """
        if self.on_media_release:
            self.on_media_release()

    def _media_setup_error(self, error):
        """Media transport setup error.
        """
        if self.on_media_setup_error:
            self.on_media_setup_error(error=error)

    def _media_transport_state_changed(self, transport, state):
        """Media transport creation/teardown.
        """
        logger.debug("Media transport is {} - {}".format(
            state, transport))
        
        self._media_transport = None
        if state == "available":
            self._media_transport = transport

        # # acquire from bluez5
        # try:
        #     mt.acquire()
        # except Exception:
        #     logger.exception("Error acquiring media transport.")
        #     if self.on_media_setup_error:
        #         self.on_media_setup_error("Error acquiring media transport.")
        #     return

    def _register_media(self, adapter):
        # build endpoint and register on DBus
        logger.debug("Building media endpoint...")
        self._media_endpoint = MediaEndpoint(
            system_bus=self._system_bus,
            configuration=MP3_CONFIGURATION)
        self._media_endpoint.on_release = self._media_release
        self._media_endpoint.on_setup_error = self._media_setup_error
        self._media_endpoint.on_transport_state_changed = \
            self._media_transport_state_changed
        logger.debug("Registering media endpoint on DBus...")
        self._media_endpoint.register(
            dbus_path="/endpoints/a2dp")

        # get Media proxy and register endpoint with bluez
        logger.debug("Fetching Media proxy...")
        self._media = Media(
            system_bus=self._system_bus,
            adapter_path=adapter.path)
        logger.debug("Registering media capabilities with bluez...")
        self._media.register(
            dbus_path="/endpoints/a2dp",
            uuid=A2DP_SINK_UUID,
            codec=MP3_CODEC,
            capabilities=MP3_CAPABILITIES)
        logger.debug("Registered and ready.")

    def _unregister_media(self):
        # unregister endpoint
        if self._media:
            logger.debug("Unregistering media objects...")
            self._media.unregister("/endpoints/a2dp")
            self._media_endpoint.unregister()
            self._media_endpoint = None
            self._media = None
            logger.debug("Unregistered media objects.")

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

