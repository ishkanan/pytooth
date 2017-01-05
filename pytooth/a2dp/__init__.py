
import logging

from pytooth.a2dp.managers import MediaManager, ProfileManager
from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger("a2dp")


class AdvancedAudioProfile:
    """Wraps up A2DP profile control via Bluez5 stack. Adapted from this Bluez4
    example:

    http://www.lightofdawn.org/wiki/wiki.cgi/BluezA2DP
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

        # media plumber
        self._mediamgr = MediaManager(
            system_bus=self._system_bus)
        self._mediamgr.on_streaming_state_changed = \
            self._streaming_state_changed
        self._mediamgr.on_unexpected_release = \
            self._media_unexpected_release
        self._mediamgr.on_transport_connect = \
            self._media_transport_connect
        self._mediamgr.on_transport_disconnect = \
            self._media_transport_disconnect

        # public events
        self.on_adapter_connected_changed = None
        self.on_adapter_properties_changed = None
        self.on_media_transport_connect = None
        self.on_media_transport_disconnect = None
        self.on_streaming_state_changed = None

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
            try:
                self._mediamgr.start(adapter=adapter)
            except Exception:
                logging.exception("Error establishing media connection.")
        else:
            logger.info("Adapter disconnected.")
            try:
                self._mediamgr.stop(adapter=adapter)
            except Exception:
                logging.exception("Error releasing media connection.")

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

    def _media_unexpected_release(self, adapter):
        """Unexpected endpoint release.
        """
        logger.debug("Media endpoint unexpectedly released on adapter {}."
            "".format(adapter))

    def _media_transport_connect(self, adapter, transport):
        """Media streaming path available. Does not imply streaming has started.
        """
        logger.debug("Media streaming path {} is available on adapter {}."
            "".format(transport, adapter))

        if self.on_media_transport_connect:
            self.on_media_transport_connect(
                adapter=adapter,
                transport=transport)

    def _media_transport_disconnect(self, adapter, transport):
        """Media streaming path released.
        """
        logger.debug("Media streaming path {} is released on adapter {}."
            "".format(transport, adapter))

        if self.on_media_transport_disconnect:
            self.on_media_transport_disconnect(
                adapter=adapter,
                transport=transport)

    def _streaming_state_changed(self, adapter, transport, state):
        """Streaming state has changed.
        """
        logger.debug("Media streaming state for adapter {} is now {}.".format(
            adapter, state))

        if self.on_streaming_state_changed:
            self.on_streaming_state_changed(
                adapter=adapter,
                transport=transport,
                state=state)

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
