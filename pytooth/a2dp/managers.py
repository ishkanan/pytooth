"""Defines objects that provide high-level control of key A2DP functions.
"""

from functools import partial
import logging

from gi.repository.GLib import Variant

from pytooth.a2dp.constants import A2DP_PROFILE_UUID, \
                                    A2DP_SINK_UUID, \
                                    A2DP_DBUS_PROFILE_ENDPOINT, \
                                    A2DP_DBUS_MEDIA_ENDPOINT, \
                                    SBC_CAPABILITIES, \
                                    SBC_CODEC, \
                                    SBC_CONFIGURATION
from pytooth.bluez5.dbus import Media, MediaEndpoint, Profile
from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages profile object interactions with bluez5. Can handle multiple
    connections with multiple remote devices.
    """

    def __init__(self, system_bus):
        self._profile = None
        self._profilemgr_proxy = Bluez5Utils.get_profilemanager(
            bus=system_bus)

        self._register_context = None
        self._started = False
        self._system_bus = system_bus

        # events
        self.on_connect = None
        self.on_disconnect = None
        self.on_unexpected_stop = None

    def start(self):
        """Starts the manager. If already started, this does nothing.
        """
        if self._started:
            return

        self._register()
        self._started = True

    def stop(self):
        """Stops the manager. If already stopped, this does nothing.
        """
        if not self._started:
            return

        try:
            self._unregister()
        except Exception:
            logger.exception("Failed to unregister profile.")
        self._started = False

    def _register(self):
        """Registers the profile implementation endpoint on DBus.
        """
        self._profile = Profile()
        self._profile.on_connect = self._profile_on_connect
        self._profile.on_disconnect = self._profile_on_disconnect
        self._profile.on_release = self._profile_on_release

        logger.debug("Registering A2DP profile on DBus...")
        self._register_context = self._system_bus.register_object(
            path=A2DP_DBUS_PROFILE_ENDPOINT,
            object=self._profile,
            node_info=None)
        self._profilemgr_proxy.RegisterProfile(
            A2DP_DBUS_PROFILE_ENDPOINT,
            A2DP_PROFILE_UUID,
            {
                "Name": Variant("s", "AdvancedAudioDistribution"),
                "RequireAuthentication": Variant("b", True),
                "RequireAuthorization": Variant("b", False),
            })
        logger.debug("Registered A2DP profile on DBus.")

    def _unregister(self):
        """Unregisters the profile endpoint on DBus.
        """
        try:
            self._profilemgr_proxy.UnregisterProfile(
                A2DP_DBUS_PROFILE_ENDPOINT)
        except Exception:
            logger.exception("Error unregistering profile endpoint.")

        if self._register_context:
            self._register_context.unregister()
            self._register_context = None
        self._profile = None

    def _profile_on_connect(self, device, fd, fd_properties):
        """New service-level connection has been established.
        """
        if self.on_connect:
            self.on_connect(
                device=device,
                fd=fd,
                fd_properties=fd_properties)

    def _profile_on_disconnect(self, device):
        """Device is disconnected from profile.
        """
        if self.on_disconnect:
            self.on_disconnect(
                device=device)

    def _profile_on_release(self):
        """Profile is unregistered.
        """
        # unexpected?
        if self._started and self.on_unexpected_stop:
            self.stop()
            self.on_unexpected_stop()

class MediaManager:
    """Manages media object interactions with bluez5. Can handle media
    connections via multiple adapters.
    """
    _endpoint_id = 1

    def __init__(self, system_bus):
        # handle connections via multiple adapters
        self._connections = {} # adapter: {media, endpoint}
        self._system_bus = system_bus

        # events
        self.on_unexpected_release = None
        self.on_transport_connect = None
        self.on_transport_disconnect = None

        # subscribe to property changes
        system_bus.subscribe(
            iface=Bluez5Utils.PROPERTIES_INTERFACE,
            signal="PropertiesChanged",
            arg0=Bluez5Utils.MEDIA_INTERFACE,
            signal_fired=self._media_properties_changed)

    def start(self, adapter):
        """Starts a media connection via specified adapter. If already started,
        this does nothing.
        """
        if adapter in self._connections:
            return

        media, endpoint = self._register(adapter=adapter)
        self._connections.update({
            adapter: {
                "media": media,
                "endpoint": endpoint
            }})

    def stop(self, adapter):
        """Stops a media connection via specified adapter. If already stopped,
        this does nothing.
        """
        if adapter not in self._connections:
            return

        self._unregister(adapter)
        self._connections.pop(adapter)

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

        # # acquire from bluez5
        # try:
        #     mt.acquire()
        # except Exception:
        #     logger.exception("Error acquiring media transport.")
        #     if self.on_media_setup_error:
        #         self.on_media_setup_error("Error acquiring media transport.")
        #     return

    def _register(self, adapter):
        """Registers a media endpoint on DBus.
        """

        # get Media proxy
        logger.debug("Fetching Media proxy...")
        media = Media(
            system_bus=self._system_bus,
            adapter_path=adapter.path)

        # build endpoint and register on DBus
        logger.debug("Building media endpoint...")
        endpoint = MediaEndpoint(
            system_bus=self._system_bus,
            configuration=SBC_CONFIGURATION)
        endpoint.on_release = partial(
            self._endpoint_release,
            adapter)
        endpoint.on_transport_setup_error = partial(
            self._endpoint_transport_setup_error,
            adapter)
        endpoint.on_transport_state_changed = partial(
            self._endpoint_transport_state_changed,
            adapter)
        logger.debug("Registering media endpoint on DBus...")
        dbus_path = "{}_{}".format(
            A2DP_DBUS_MEDIA_ENDPOINT,
            MediaManager._endpoint_id)
        endpoint.register(dbus_path)

        # register endpoint with bluez5
        logger.debug("Registering media capabilities with bluez...")
        try:
            media.register(
                dbus_path=dbus_path,
                uuid=A2DP_SINK_UUID,
                codec=SBC_CODEC,
                capabilities=SBC_CAPABILITIES)
        except Exception:
            logger.exception("Error registering capabilities.")
            endpoint.unregister()
            raise

        # all good!
        endpoint.path = dbus_path
        MediaManager._endpoint_id = MediaManager._endpoint_id + 1
        logger.debug("Registered and ready.")
        return media, endpoint

    def _unregister(self, adapter):
        """Unregisters a media endpoint from DBus.
        """
        media = self._connections[adapter]["media"]
        endpoint = self._connections[adapter]["endpoint"]
        logger.debug("Unregistering media for adapter {}...".format(adapter))
        media.unregister(endpoint.path)
        endpoint.unregister()
        logger.debug("Unregistered media for adapter {}.".format(adapter))

    def _endpoint_release(self, adapter):
        """Endpoint release.
        """
        logger.debug("Media for adapter {} released by Bluez5.".format(adapter))
        
        # unregister it in case it hasn't been
        try:
            self.stop(adapter=adapter)
        except Exception:
            logger.exception("Error unregistering endpoint.")
        unexpected = adapter in self._connections
        self._connections.pop(adapter, {})

        if unexpected and self.on_unexpected_release:
            self.on_unexpected_release(adapter=adapter)

    def _endpoint_transport_setup_error(self, adapter, error):
        """Media transport setup error.
        """
        pass

    def _endpoint_transport_state_changed(self, adapter, transport, state):
        """Media transport creation/teardown.
        """
        logger.debug("Media transport {} for adapter {} is {}.".format(
            transport, adapter, state))

        if state == "available":
            # TODO: figure out how to store based on streaming transition
            # logic, no idea how to detect yet...
            if self.on_transport_connect:
                self.on_transport_connect(
                    adapter=adapter,
                    transport=transport)
        elif state == "released":
            # TODO: forget
            try:
                transport.release()
            except Exception:
                logger.exception("Error releasing transport.")
            if self.on_transport_disconnect:
                self.on_transport_disconnect(
                    adapter=adapter,
                    transport=transport)
