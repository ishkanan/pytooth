"""Defines objects that provide high-level control of key HFP functions.
"""

from functools import partial
import logging

from dbus import UInt16
from tornado.ioloop import IOLoop

from pytooth.bluez5.dbus import Profile
from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.hfp.constants import HFP_PROFILE_UUID, \
                                    HFP_DBUS_PROFILE_ENDPOINT, \
                                    HF_FEATURES
from pytooth.hfp.helpers import SerialPortConnection
from pytooth.hfp.proxy import RemotePhone

logger = logging.getLogger("hfp/"+__name__)


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

        self.io_loop = IOLoop.instance()

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
        logger.debug("Registering HFP profile on DBus...")

        self._profile = Profile(
            system_bus=self._system_bus,
            dbus_path=HFP_DBUS_PROFILE_ENDPOINT)
        self._profile.on_connect = self._profile_on_connect
        self._profile.on_disconnect = self._profile_on_disconnect
        self._profile.on_release = self._profile_on_release

        self._profilemgr_proxy.proxy.RegisterProfile(
            HFP_DBUS_PROFILE_ENDPOINT,
            "hfp-hf",
            {
                "Name": "Hands-Free",
                "Version": UInt16(0x0107),
                "Features": UInt16(HF_FEATURES),
                "RequireAuthentication": True,
                "RequireAuthorization": False,
            })
        logger.debug("Registered HFP profile on DBus.")

    def _unregister(self):
        """Unregisters the profile endpoint on DBus.
        """
        try:
            self._profilemgr_proxy.proxy.UnregisterProfile(
                HFP_DBUS_PROFILE_ENDPOINT)
        except Exception:
            logger.exception("Error unregistering profile endpoint.")

        self._profile = None

    def _profile_on_connect(self, device, fd, fd_properties):
        """New RFCOMM connection has been established.
        """

        try:
            conn = SerialPortConnection(
                fd=fd,
                async_reply_delay=5,
                io_loop=self.io_loop)
        except Exception:
            logging.exception("SerialPortConnection instantiation error.")
            return

        # hand remote phone proxy to something that cares
        phone = RemotePhone(
            connection=conn,
            io_loop=self.io_loop)
        if self.on_connect:
            self.on_connect(
                device=device,
                phone=phone)

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
        if self._started:
            self.stop()
            if self.on_unexpected_stop:
                self.on_unexpected_stop()
