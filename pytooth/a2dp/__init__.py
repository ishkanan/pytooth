
import logging
import socket

from pytooth.a2dp.managers import MediaManager, ProfileManager
from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class AdvancedAudioProfile:
    """Top-level class for A2DP control via Bluez5 stack.
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
        pmgr = ProfileManager(system_bus=system_bus)
        pmgr.on_connected_changed = self._profile_connected_changed
        pmgr.on_unexpected_stop = self._profile_unexpected_stop
        self._profilemgr = pmgr

        # media plumber
        mmgr = MediaManager(system_bus=self._system_bus)
        mmgr.on_media_setup_error = self._media_setup_error
        mmgr.on_stream_state_changed = self._media_stream_state_changed
        mmgr.on_track_changed = self._media_track_changed
        mmgr.on_unexpected_release = self._media_unexpected_release
        self._mediamgr = mmgr

        # public events
        self.on_adapter_connected_changed = None
        self.on_audio_setup_error = None
        self.on_audio_stream_state_changed = None
        self.on_audio_track_changed = None
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
        self._mediamgr.stop(adapter=self._adapter)
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

            try:
                self._mediamgr.start(adapter=self._adapter)
            except Exception:
                logger.exception("Error starting media manager.")
                if self.on_audio_setup_error:
                    self.on_audio_setup_error(
                        adapter=None,
                        error="Error starting media manager.")
        else:
            logger.info("Adapter '{}' disconnected.".format(
                adapter.last_address))

            try:
                self._mediamgr.stop(adapter=adapter)
            except Exception:
                logging.exception("Error releasing media connection.")

        if self.on_adapter_connected_changed:
            self.on_adapter_connected_changed(adapter, connected)

    def _adapter_properties_changed(self, adapter, props):
        """Adapter properties changed.
        """
        logger.info("Adapter '{}' properties changed - {}".format(
            adapter.address,
            props))

    def _media_setup_error(self, adapter, error):
        """Error starting media streaming.
        """
        if self.on_audio_setup_error:
            self.on_audio_setup_error(
                adapter=adapter,
                error=error)

    def _media_stream_state_changed(self, adapter, transport, state):
        """Streaming state has changed (stopped, paused, playing).
        """
        if self.on_audio_stream_state_changed:
            self.on_audio_stream_state_changed(
                adapter=adapter,
                transport=transport,
                state=state)

    def _media_track_changed(self, track):
        """Streaming track has changed.
        """
        if self.on_audio_track_changed:
            self.on_audio_track_changed(track=track)
            
    def _media_unexpected_release(self, adapter):
        """Unexpected media endpoint release (something messing with Bluez5
        perhaps).
        """
        if self.on_audio_setup_error:
            self.on_audio_setup_error(
                adapter=adapter,
                error="Lost media connection with Bluez5.")

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
