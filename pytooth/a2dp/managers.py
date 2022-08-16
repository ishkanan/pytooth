"""Defines objects that provide high-level control of key A2DP functions.
"""

from functools import partial
import logging

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

        self._started = False
        self._system_bus = system_bus

        # events
        self.on_connected_changed = None
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

        self._unregister()
        self._started = False

    @property
    def started(self):
        return self._started

    def _register(self):
        """Registers the profile implementation endpoint on DBus.
        """
        logger.debug("Registering A2DP profile on DBus...")

        self._profile = Profile(
            system_bus=self._system_bus,
            dbus_path=A2DP_DBUS_PROFILE_ENDPOINT)
        self._profile.on_connect = self._profile_on_connect
        self._profile.on_disconnect = self._profile_on_disconnect
        self._profile.on_release = self._profile_on_release

        self._profilemgr_proxy.RegisterProfile(
            A2DP_DBUS_PROFILE_ENDPOINT,
            A2DP_PROFILE_UUID,
            {
                "Name": "AdvancedAudioDistribution",
                "RequireAuthentication": True,
                "RequireAuthorization": False,
            })
        logger.debug("Registered A2DP profile on DBus.")

    def _unregister(self):
        """Unregisters the profile endpoint on DBus.
        """
        try:
            self._profilemgr_proxy.UnregisterProfile(
                A2DP_DBUS_PROFILE_ENDPOINT)
            logger.debug("Unregistered A2DP profile.")
        except Exception:
            logger.exception("Error unregistering profile endpoint.")

        self._profile = None

    def _profile_on_connect(self, device, fd, fd_properties):
        """New service-level connection has been established.
        """
        if self.on_connected_changed:
            self.on_connected_changed(
                device=device,
                connected=True)

    def _profile_on_disconnect(self, device):
        """Device is disconnected from profile.
        """
        if self.on_connected_changed:
            self.on_connected_changed(
                device=device,
                connected=False)

    def _profile_on_release(self):
        """Profile is unregistered.
        """
        # unexpected?
        if self._started:
            self.stop()
            if self.on_unexpected_stop:
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

        # public events
        self.on_media_setup_error = None
        self.on_stream_state_changed = None
        self.on_track_changed = None
        self.on_unexpected_release = None

        # subscribe to property changes
        # system_bus.add_signal_receiver(
        #     handler_function=self._player_properties_changed,
        #     signal_name="PropertiesChanged",
        #     dbus_interface=Bluez5Utils.PROPERTIES_INTERFACE,
        #     arg0=Bluez5Utils.MEDIA_PLAYER_INTERFACE,
        #     path_keyword="path")

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
                "endpoint": endpoint,
                "streamstatus": None,
                "transport": None
            }})
        adapter.on_properties_changed = self._player_properties_changed

    def stop(self, adapter):
        """Stops a media connection via specified adapter. If already stopped,
        this does nothing.
        """
        if adapter not in self._connections:
            return

        self._unregister(adapter)
        adapter.on_properties_changed = None
        self._connections.pop(adapter)

    @property
    def started(self):
        return self._started

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
        dbus_path = "{}_{}".format(
            A2DP_DBUS_MEDIA_ENDPOINT,
            MediaManager._endpoint_id)
        endpoint = MediaEndpoint(
            system_bus=self._system_bus,
            dbus_path=dbus_path,
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
        logger.debug("Registered media endpoint on DBus.")

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
            raise

        # all good!
        endpoint.path = dbus_path
        MediaManager._endpoint_id = MediaManager._endpoint_id + 1
        logger.debug("Registered and ready.")
        return media, endpoint

    def _unregister(self, adapter):
        """Unregisters a media endpoint from DBus.
        """
        conn = self._connections[adapter]
        logger.debug("Unregistering media for adapter {} ...".format(adapter))
        conn["media"].unregister(conn["endpoint"].path)
        logger.debug("Unregistered media for adapter {}".format(adapter))

    def _player_properties_changed(self, adapter, interface, props):
        """Fired by the adapter when a Bluez property changes.
        """
        # only care about Media Player changes
        if interface != Bluez5Utils.MEDIA_PLAYER_INTERFACE:
            return

        # ignore the frequent single "position" updates
        if len(props) == 1 and "Position" in props:
            return

        logger.debug("SIGNAL: path={}, interface={}, props={}".format(
            adapter.path, interface, props))

        # just to be safe, check if tracking adapter
        if adapter not in self._connections.items():
            logger.debug("Adapter not tracked, ignoring signal.")
            return

        # report back track update
        if "Track" in props:
            if self.on_track_changed:
                self.on_track_changed(
                    track=props["Track"])

        # streaming status update
        if "Status" in props:
            self._update_stream_status(
                adapter=adapter,
                status=props["Status"])

    def _update_stream_status(self, adapter, status):
        """Performs actions based on newly-received streaming status.
        """
        context = self._connections[adapter]
        context["streamstatus"] = status
        transport = context["transport"]

        # transport could be released by bluez which is weird but possible
        if not transport:
            logger.warning("Bluez5 released the transport, will not attempt "
                "to acquire it.")
        else:
            # acquire the transport to begin receiving data
            # note: transport release is either manual or implicit when
            #       a remote device disconnects
            if not transport.acquired and status == "playing":
                try:
                    transport.acquire()
                except Exception as e:
                    logger.exception(e)
                    if self.on_media_setup_error:
                        self.on_media_setup_error(
                            adapter=adapter,
                            error="{}".format(e))
            elif status in ["paused", "stopped"]:
                # playback stopped, so release the transport
                try:
                    transport.release()
                    if self.on_stream_state_changed:
                        self.on_stream_state_changed(
                            adapter=adapter,
                            transport=transport,
                            state="released")
                except Exception as e:
                    logger.exception(e)

        # state update
        if self.on_stream_state_changed:
            self.on_stream_state_changed(
                adapter=adapter,
                transport=transport,
                state=status)

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
        """Media transport setup error. This is different to an acquisition
        error.
        """
        if self.on_media_setup_error:
            self.on_media_setup_error(
                adapter=adapter,
                error=error)

    def _endpoint_transport_state_changed(self, adapter, transport, available):
        """Media transport path creation/teardown. This is different to stream
        start/stop.
        """
        logger.debug("Media transport {} for adapter {} is {}.".format(
            transport, adapter, "available" if available else "released"))

        if available:
            self._connections[adapter]["transport"] = transport
        else:
            if self.on_stream_state_changed:
                self.on_stream_state_changed(
                    adapter=adapter,
                    transport=transport,
                    state="released")
            self._connections[adapter]["transport"] = None
