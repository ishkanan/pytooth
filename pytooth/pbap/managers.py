"""Defines objects that provide high-level control of key HFP functions.
"""

import logging

from dbus import UInt16
from tornado.ioloop import IOLoop

from pytooth.bluez5.dbus import ObexSessionFactory, PhonebookClient, Profile
from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.pbap.constants import PBAP_PROFILE_UUID, \
                                    PBAP_DBUS_PROFILE_ENDPOINT

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

        self.io_loop = IOLoop.instance()

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

        try:
            self._unregister()
        except Exception:
            logger.exception("Failed to unregister profile.")
        self._started = False

    def _register(self):
        """Registers the profile implementation endpoint on DBus.
        """
        logger.debug("Registering PBAP profile on DBus...")

        self._profile = Profile(
            system_bus=self._system_bus,
            dbus_path=PBAP_DBUS_PROFILE_ENDPOINT)
        self._profile.on_connect = self._profile_on_connect
        self._profile.on_disconnect = self._profile_on_disconnect
        self._profile.on_release = self._profile_on_release

        self._profilemgr_proxy.proxy.RegisterProfile(
            PBAP_DBUS_PROFILE_ENDPOINT,
            PBAP_PROFILE_UUID,
            {
                "Name": "Phonebook Access Profile",
                "Version": UInt16(0x0102),
                "Features": 0,
                "RequireAuthentication": True,
                "RequireAuthorization": False,
            })
        logger.debug("Registered PBAP profile on DBus.")

    def _unregister(self):
        """Unregisters the profile endpoint on DBus.
        """
        try:
            self._profilemgr_proxy.proxy.UnregisterProfile(
                PBAP_DBUS_PROFILE_ENDPOINT)
        except Exception:
            logger.exception("Error unregistering profile endpoint.")

        self._profile = None

    def _profile_on_connect(self, device, socket, fd_properties):
        """New RFCOMM connection has been established.
        """

        # TODO: is this a thing?

        # hand client proxy to something that cares
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

class ClientManager:
    """Manages the creation and destruction of client connections to PBAP
    servers, and the required underlying Obex sessions. Note this will only
    allow one active session/client pair per remote PBAP server.
    """

    def __init__(self, system_bus):
        # key: destination address
        # value: PhonebookClient instance
        self._clients = None
        self._factory = ObexSessionFactory(
            system_bus=system_bus)
        self._started = False

    def start(self):
        """Starts the manager. If already started, this does nothing.
        """
        if self._started:
            return

        self._clients = {}
        self._started = True

    def stop(self):
        """Stops the manager. If already stopped, this does nothing.
        """
        if not self._started:
            return

        # close any remaining sessions
        for dest, client in self._clients.items():
            try:
                client.proxy.
            try:
                self._unregister()
            except Exception as e:
                logger.error("Error closing Obex session to {}.".format())
        self._clients = None
        self._started = False

    def connect(self, destination):
        pass
