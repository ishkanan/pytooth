"""Defines objects that provide high-level control of key HFP functions.
"""

import logging

from dbus import UInt16

from pytooth.bluez5.dbus import ObexSessionFactory, PhonebookClient, Profile
from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.errors import InvalidOperationError
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
            logger.debug("Unregistered PBAP profile.")
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
    allow one client per session/client pair per remote PBAP server.
    """

    def __init__(self, session_bus):
        # key: destination address
        # value: PhonebookClient instance
        self._clients = None
        self._factory = ObexSessionFactory(
            session_bus=session_bus)
        self._started = False
        self._session_bus = session_bus

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

        # close any open sessions
        logger.debug("Disconnecting {} forgotten Obex session(s)...".format(
            len(self._clients)))
        for dest, _ in dict(self._clients).items():
            try:
                self.disconnect(destination=dest)
            except ConnectionError:
                pass
        self._clients = None
        self._started = False

    def connect(self, destination):
        """Establishes a connection to a remote PBAP server. If a connection
        to the specified server is already being tracked, this returns the
        client for that connection. If not started, this raises an
        `InvalidOperationError` error. If connection failed, this raises a
        `ConnectionError` error.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if destination in self._clients:
            return self._clients[destination]

        session = self._factory.create_session(
            destination=destination,
            target="pbap")
        try:
            self._clients[destination] = PhonebookClient(
                session_bus=self._session_bus,
                session=session)
            logger.debug("Obex session to '{}' has been established.".format(
                destination))
            return self._clients[destination]
        except Exception:
            logger.exception("Error creating Obex session to '{}'.".format(
                destination))
            try:
                self._factory.destroy_session(session=session)
            except Exception:
                logger.exception("Error disconnecting Obex session to '{}'.".format(destination))
            raise ConnectionError("Error connecting to '{}'.".format(
                destination))

    def disconnect(self, destination):
        """Closes the connection to a remote PBAP server. If a connection does
        not exist, this does nothing. If not started, this raises an
        `InvalidOperationError` error. If an error occurred when disconnecting,
        this raises a `ConnectionError` error.
        """
        if not self._started:
            raise InvalidOperationError("Not started.")
        if destination not in self._clients:
            return

        try:
            self._clients[destination].abort()
            self._factory.destroy_session(
                session=self._clients[destination].session)
            logger.debug("Obex session to '{}' has been disconnected.".format(
                destination))
        except Exception:
            logger.exception("Error disconnecting Obex session to '{}'.".format(
                destination))
            raise ConnectionError("Error disconnecting from '{}'.".format(
                destination))
        finally:
            self._clients.pop(destination)

    def get_client(self, destination):
        """Returns the client, if any, associated with the connection to
        device specified by `destination`. This returns None if no connection
        is present.
        """
        return self._clients.get(destination)
