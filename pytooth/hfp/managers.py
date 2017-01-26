"""Defines objects that provide high-level control of key HFP functions.
"""

from functools import partial
import logging
from socket import AF_BLUETOOTH, BTPROTO_SCO, SOCK_SEQPACKET, socket

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
        if self.on_connected_changed:
            self.on_connected_changed(
                device=device,
                connected=True,
                phone=phone)

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
    """Manages SCO audio connections with bluez5. When a connection is
    received, stop() is internally called. The caller must call start() again
    when suitable to accept a new connection. Can handle media connections via
    multiple adapters.
    """

    def __init__(self):
        # socket
        self._connections = {} # adapter: {socket, loophandle}

        # public events
        self.on_media_connected = None
        self.on_media_setup_error = None

    def start(self, adapter):
        """Begins listening for a media connection via specified adapter. If
        already listening on specified adapter, this does nothing.
        """
        if adapter in self._connections:
            return

        socket, loophandle = self._sco_listen()
        self._connections.update({
            adapter: {
                "socket": socket,
                "loophandle": loophandle
            }})

    def stop(self, adapter):
        """Stops listening for a media connection via specified adapter. If
        not listening on specified adapter, this does nothing.
        """
        if adapter not in self._connections:
            return

        self._sco_close(adapter)
        self._connections.pop(adapter)

    def _sco_listen(self, adapter):
        """Helper to set up a listening SCO socket.
        """
        try:
            # raw socket
            sock = socket(AF_BLUETOOTH, SOCK_SEQPACKET, BTPROTO_SCO)
            sock.setblocking(0)
            sock.bind(adapter.address)
            sock.listen(1)

            # connection accepter
            handle = self.io_loop.add_handler(
                sock.fileno(),
                partial(self._connection_ready, adapter=adapter),
                IOLoop.READ)

            return socket, handle
        except Exception:
            self._sco_close()
            raise

    def _sco_close(self, adapter):
        """Helper to close an SCO socket.
        """
        try:
            socket = self._connections[adapter]["socket"]
            handle = self._connections[adapter]["loophandle"]
            socket.close()
        except Exception:
            logger.exception("Socket cleanup error.")
        finally:
            self._socket = None
            self._stream = None

    def _connection_ready(self, adapter, fd, events):
        """Callback for a new connection.
        """
        try:
            (connection, peer) = self._socket.accept()
        except Exception:
            lo
        logger.info("Accepted SCO audio connection from {} via adapter {}"
            "".format(peer, adapter))
        
        # caller to start listening again
        self.stop(adapter)

        if self.on_media_connected:
            self.on_media_connected(
                adapter=adapter,
                socket=connection,
                peer=peer)
