
import logging

from pytooth.hfp.managers import MediaManager, ProfileManager

logger = logging.getLogger(__name__)


class HandsFreeProfile:
    """Top-level class for HFP control via Bluez5 stack.
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

        # media plumber
        mmgr = MediaManager()
        mmgr.on_media_connected_changed = self._media_connected_changed
        mmgr.on_media_setup_error = self._media_setup_error
        self._mediamgr = mmgr

        # public events
        self.on_adapter_connected_changed = None
        self.on_audio_connected_changed = None
        self.on_audio_setup_error = None
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
                logging.exception("Error stopping media manager.")

        if self.on_adapter_connected_changed:
            self.on_adapter_connected_changed(adapter, connected)

    def _adapter_properties_changed(self, adapter, props):
        """Adapter properties changed.
        """
        logger.info("Adapter '{}' properties changed - {}".format(
            adapter.address,
            props))

    def _media_connected_changed(self, adapter, connected, socket, mtu, peer):
        """A media connection has been established or closed.
        """
        if self.on_audio_connected_changed:
            self.on_audio_connected_changed(
                adapter=adapter,
                connected=connected,
                socket=socket,
                mtu=mtu,
                peer=peer)

        if not connected:
            self._mediamgr.start(adapter=adapter)

    def _media_setup_error(self, adapter, error):
        """Error setting up media connection.
        """
        if self.on_audio_setup_error:
            self.on_audio_setup_error(
                adapter=adapter,
                error=error)

        # try listening again if we are not
        # note: potential cause of log spam!
        if self._mediamgr.status(adapter=adapter) == "idle":
            logger.debug("Going to restart MediaManager instance in 10s...")
            self.io_loop.call_later(10, self._mediamgr.start, adapter=adapter)

    def _profile_connected_changed(self, device, connected, phone):
        """Service-level connection has been established or ended with a
        remote device.
        """
        logger.debug("Device {} is now {}.".format(
            device, "connected" if connected else "disconnected"))

        if self.on_device_connected_changed:
            self.on_device_connected_changed(
                device=device,
                connected=connected,
                phone=phone)

        # initiate handshake only after higher-level classes are alerted so
        # they can subscribe to relevant events
        phone.start()

    def _profile_unexpected_stop(self):
        """Profile was unregistered without our knowledge (something messing
        with Bluez5 perhaps).
        """
        logger.error("Profile unexpectedly unregistered.")

        if self.on_profile_status_changed:
            self.on_profile_status_changed(available=False)
