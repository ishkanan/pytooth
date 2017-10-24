"""Defines objects that provide high-level control of key HFP functions.
"""

from functools import partial
import logging
from socket import AF_BLUETOOTH, BTPROTO_SCO, SOCK_SEQPACKET, socket

from dbus import UInt16
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream

from pytooth.bluez5.dbus import Profile
from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.hfp.constants import HFP_PROFILE_UUID, \
                                    HFP_DBUS_PROFILE_ENDPOINT, \
                                    HF_SUPPORTED_FEATURES
from pytooth.hfp.helpers import SerialPortConnection
from pytooth.hfp.proxy import RemotePhone

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
                "Features": UInt16(HF_SUPPORTED_FEATURES),
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

    def _profile_on_connect(self, device, socket, fd_properties):
        """New RFCOMM connection has been established.
        """

        try:
            conn = SerialPortConnection(
                socket=socket,
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
        # adapter to socket map
        self._connections = {} # adapter: {socket, IOStream}

        self.io_loop = IOLoop.instance()

        # public events
        self.on_media_connected_changed = None
        self.on_media_setup_error = None

    def status(self, adapter):
        """Returns the status of a particular adapter with respect to SCO
        connections.
        """
        if adapter not in self._connections:
            return "Idle"
        if "stream" not in self._connections[adapter]:
            return "Listening"
        return "Connected"

    def start(self, adapter):
        """Begins listening for a media connection via specified adapter. If
        already listening or established on adapter, this does nothing.
        """
        if adapter in self._connections:
            return

        # attempt to create listening socket
        try:
            self._connections[adapter] = {
                "socket": self._sco_listen(adapter)
            }
        except Exception as e:
            logger.exception("Failed to make SCO listen socket on adapter {}"
                "".format(adapter))
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="Failed to make SCO listen socket - {}".format(e))
            return
        logger.debug("Listening for SCO connection on adapter {}".format(
            adapter))

    def stop(self, adapter):
        """Stops listening or closes media connection via specified adapter. If
        not listening or established on adapter, this does nothing.
        """
        if adapter not in self._connections:
            return

        self._sco_close(adapter)
        self._connections.pop(adapter)

    def _sco_listen(self, adapter):
        """Helper to set up a listening SCO socket.
        """

        # obviously requires SCO socket support in the OS
        try:
            sock = socket(AF_BLUETOOTH, SOCK_SEQPACKET, BTPROTO_SCO)
            sock.setblocking(0)
            sock.bind(adapter.address.encode())
            sock.listen(1)
        except Exception:
            if sock:
                sock.close()
            raise

        # connection accepter
        self.io_loop.add_handler(
            sock.fileno(),
            partial(self._sco_connection_ready, adapter=adapter),
            IOLoop.READ)

        return sock

    def _sco_close(self, adapter):
        """Helper to close a listening or established SCO socket.
        """
        try:
            sock = self._connections[adapter]["socket"]
            self.io_loop.remove_handler(sock.fileno())
            sock.close()
        except KeyError:
            logger.warning("Ignored SCO close attempt for adapter {} as it is "
                "not being tracked.".format(adapter))
        except Exception:
            logger.exception("SCO socket close error for adapter {}".format(
                adapter))

    def _sco_connection_ready(self, fd, events, adapter):
        """Callback for a new SCO connection.
        """

        # accept new socket
        try:
            (sock, peer) = self._connections[adapter]["socket"].accept()
        except Exception as e:
            logger.exception("SCO socket accept error for adapter {}".format(
                adapter))
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="SCO socket accept error - {}".format(e))
            return
        
        # get SCO MTU
        try:
            mtu = sock.getsockopt(17, 1)
            logger.debug("SCO MTU for adapter = {}".format(adapter, mtu))
        except Exception as e:
            logger.exception("SCO MTU retrieve error for adapter {}".format(
                adapter))
            sock.close()
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="SCO MTU retrieve error - {}".format(e))
            return

        # check CVSD mode is good
        # note: this will need altering if we add support for mSBC
        try:
            mode = sock.getsockopt(274, 11)
            logger.debug("CVSD sample format ID for adapter {} = {}".format(
                adapter, mode))
            if mode != 96: # 16-bit signed LE samples
                if self.on_media_setup_error:
                    self.on_media_setup_error(
                        adapter=adapter,
                        error="Unsupported CVSD sample format - {}"
                            ", 16-bit signed LE required.".format(mode))
                return
        except Exception as e:
            logger.exception("CVSD sample format ID retrieve error for adapter "
                "{}".format(adapter))
            sock.close()
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="CVSD sample format ID retrieve error - {}".format(e))
            return

        # close listening socket
        self._connections[adapter]["socket"].close()

        # connection close detection
        # note: we only read via the socket, never via the stream
        stream = IOStream(socket=sock)
        stream.set_close_callback(
            callback=partial(self._sco_on_established_closed, adapter=adapter))
        self._connections[adapter] = {
            "socket": sock,
            "stream": stream
        }

        # can finally safely announce new connection
        logger.info("New SCO connection from peer {} for adapter {}".format(
            peer, adapter))

        if self.on_media_connected_changed:
            self.on_media_connected_changed(
                adapter=adapter,
                connected=True,
                socket=sock,
                mtu=mtu,
                peer=peer)

    def _sco_on_established_closed(self, adapter):
        """Called by Tornado when an established SCO socket closes.
        """
        logger.debug("Established SCO socket has closed for adapter {}.".format(
            adapter))

        if adapter in self._connections:
            # stop() wasn't called
            self.stop(adapter=adapter)
            if self.on_media_connected_changed:
                self.on_media_connected_changed(
                    adapter=adapter,
                    connected=False,
                    socket=None,
                    mtu=None,
                    peer=None)
