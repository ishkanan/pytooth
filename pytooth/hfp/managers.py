"""Defines objects that provide high-level control of key HFP functions.
"""

from functools import partial
import logging
import select
from socket import AF_BLUETOOTH, BTPROTO_SCO, SOCK_SEQPACKET, socket

from dbus import UInt16
from tornado.ioloop import IOLoop

from pytooth.bluez5.dbus import Profile
from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.hfp.constants import HFP_DBUS_PROFILE_ENDPOINT, HF_SUPPORTED_FEATURES
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
            logger.debug("Unregistered HFP profile.")
        except Exception:
            logger.exception("Error unregistering profile endpoint.")

        self._profile = None

    def _profile_on_connect(self, device, socket, fd_properties):
        """New RFCOMM connection has been established.
        """

        try:
            conn = SerialPortConnection(
                socket=socket,
                device_path=device,
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
        self._connections = {}  # adapter: {socket}

        self.io_loop = IOLoop.instance()

        # public events
        self.on_media_connected_changed = None
        self.on_media_setup_error = None

    def status(self, adapter):
        """Returns the status of a particular adapter with respect to SCO
        connections.
        """
        if adapter not in self._connections:
            return "idle"
        return self._connections[adapter]["status"]

    def start(self, adapter):
        """Begins listening for a media connection via specified adapter. If
        already listening or established on adapter, this does nothing.
        """
        if adapter in self._connections:
            return

        # attempt to create listening socket
        try:
            self._connections[adapter] = {
                "socket": self._sco_listen(adapter),
                "status": "listening"
            }
        except Exception as e:
            logger.exception("Failed to make SCO listen socket on adapter {}".format(adapter))
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="Failed to make SCO listen socket - {}".format(e))
            return
        logger.debug("Listening for SCO connection on adapter {}".format(adapter))

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
            ep = self._connections[adapter].get("epoll")
            if ep:
                # ep.unregister(sock)
                ep.close()
            if self._connections[adapter]["status"] == "listening":
                self.io_loop.remove_handler(sock.fileno())
            sock.close()
            logger.debug("Successfully closed listening SCO socket on adapter {}".format(adapter))
        except KeyError:
            logger.warning("Ignored SCO close attempt for adapter {} as it is "
                           "not being tracked.".format(adapter))
        except Exception:
            logger.exception("SCO socket close error for adapter {}".format(adapter))

    def _sco_connection_ready(self, fd, events, adapter):
        """Callback for a new SCO connection.
        """

        # accept new socket
        try:
            (sock, peer) = self._connections[adapter]["socket"].accept()
        except Exception as e:
            logger.exception("SCO socket accept error for adapter {}".format(adapter))
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="SCO socket accept error - {}".format(e))
            return

        # get SCO MTU
        try:
            mtu = sock.getsockopt(17, 1)
            logger.debug("SCO MTU for adapter {} = {}".format(adapter, mtu))
        except Exception as e:
            logger.exception("SCO MTU retrieve error for adapter {}".format(adapter))
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
            if mode != 96:  # 16-bit signed LE samples
                if self.on_media_setup_error:
                    self.on_media_setup_error(
                        adapter=adapter,
                        error="Unsupported CVSD sample format - {}"
                              ", 16-bit signed LE required.".format(mode))
                return
        except Exception as e:
            logger.exception("CVSD sample format ID retrieve error for adapter {}".format(adapter))
            sock.close()
            if self.on_media_setup_error:
                self.on_media_setup_error(
                    adapter=adapter,
                    error="CVSD sample format ID retrieve error - {}".format(e))
            return

        # close listening socket and remember established one
        self._connections[adapter]["socket"].close()
        self._connections[adapter] = {
            "socket": sock,
            "status": "connected"
        }

        # connection close detection
        ep = select.epoll()
        ep.register(sock, select.EPOLLERR | select.EPOLLHUP)
        self._connections[adapter]["epoll"] = ep
        self.io_loop.add_callback(
            callback=partial(self._sco_close_check, adapter=adapter))

        # can finally safely announce new connection
        logger.info("SCO connection established by peer {} for adapter {}".format(
            peer, adapter))

        if self.on_media_connected_changed:
            self.on_media_connected_changed(
                adapter=adapter,
                connected=True,
                socket=sock,
                mtu=mtu,
                peer=peer)

    def _sco_close_check(self, adapter):
        """Constantly called to check if an established SCO socket has closed.
        """

        # if stop() was called, the adapter won't be tracked, so stop checking
        if adapter not in self._connections:
            return

        ep = self._connections[adapter]["epoll"]
        sock = self._connections[adapter]["socket"]
        closed = False

        try:
            # timeout of 0 means no blocking
            result = ep.poll(1.0)
            closed = len(result) != 0
        except Exception as e:
            # assuming any error with the socket is a close
            logger.error("EPOLL error in _sco_close_check() - {}".format(e))
            closed = True

        if closed:
            logger.info("An established SCO socket has closed on adapter {}.".format(adapter))
            self.stop(adapter=adapter)
            if self.on_media_connected_changed:
                self.on_media_connected_changed(
                    adapter=adapter,
                    connected=False,
                    socket=sock,
                    mtu=None,
                    peer=None)
        else:
            self.io_loop.call_later(
                delay=1,
                callback=self._sco_close_check,
                adapter=adapter)
