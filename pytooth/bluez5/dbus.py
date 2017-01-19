"""Provides stubs for required callable DBus objects.
https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc
"""

import dbus
import logging
import os

from gi.repository.GLib import Variant

from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.errors import InvalidOperationError

logger = logging.getLogger("bluez5/"+__name__)


class Media:
    """Encapsulates a Media bluez5 object.
    """

    def __init__(self, system_bus, adapter_path):
        self._media_proxy = Bluez5Utils.get_media(
            bus=system_bus,
            adapter_path=adapter_path)

    def register(self, dbus_path, uuid, codec, capabilities):
        """Registers our capabilities with bluez5.
        """
        self._media_proxy.proxy.RegisterEndpoint(
            dbus_path,
            {
                "UUID": Variant("s", uuid),
                "Codec": Variant("y", codec),
                "Capabilities": Variant("ay", capabilities)
            })

    def unregister(self, dbus_path):
        """Unregisters our capabilities with bluez5.
        """
        self._media_proxy.proxy.UnregisterEndpoint(dbus_path)

class MediaEndpoint(dbus.service.Object):
    """Encapsulates a MediaEndpoint bluez5 object.
    """

    def __init__(self, system_bus, dbus_path, configuration):
        super().__init__(self, system_bus, dbus_path)

        self._configuration = configuration # desired
        self._transport = None
        self._system_bus = system_bus

        self.on_release = None
        self.on_transport_setup_error = None
        self.on_transport_state_changed = None

    @dbus.service.method(dbus_interface=Bluez5Utils.MEDIA_ENDPOINT_INTERFACE,
                         in_signature="oa{sv}", out_signature=None)
    def SetConfiguration(self, transport, properties):
        """Invoked by bluez5 when the transport configuration has been set.
        """
        logger.debug("Media endpoint config set - {}".format(properties))
        logger.debug("Media transport is available - {}".format(transport))

        # build media transport
        try:
            self._transport = MediaTransport(
                system_bus=self._system_bus,
                transport_path=transport)
        except Exception as ex:
            logger.exception("Error fetching media transport.")
            if self.on_transport_setup_error:
                self.on_transport_setup_error(ex)
            return

        # hand out
        if self.on_transport_state_changed:
            self.on_transport_state_changed(
                transport=self._transport,
                state="available")

    @dbus.service.method(dbus_interface=Bluez5Utils.MEDIA_ENDPOINT_INTERFACE,
                         in_signature="ab", out_signature="ab")
    def SelectConfiguration(self, capabilities):
        """Invoked by bluez5 when negotiating transport configuration with us.
        """
        logger.debug("Media endpoint capabilities - {}".format(capabilities))
        return self._configuration

    @dbus.service.method(dbus_interface=Bluez5Utils.MEDIA_ENDPOINT_INTERFACE,
                         in_signature="o", out_signature=None)
    def ClearConfiguration(self, transport):
        """Invoked by bluez5 when it is forgetting configuration because the
        transport was stopped.
        """
        logger.debug("Bluez5 has cleared the configuration for transport - {}"
            "".format(transport))
        if self.on_transport_state_changed:
            self.on_transport_state_changed(
                transport=self._transport,
                state="released")
            self._transport = None

    @dbus.service.method(dbus_interface=Bluez5Utils.MEDIA_ENDPOINT_INTERFACE,
                         in_signature=None, out_signature=None)
    def Release(self):
        """Invoked when bluez5 shuts down.
        """
        if self.on_release:
            self.on_release()

class MediaTransport:
    """Encapsulates a bluez5 MediaTransport object.
    """

    def __init__(self, system_bus, dbus_path):
        self._system_bus = system_bus
        self._proxy = Bluez5Utils.get_media_transport(
            bus=self._system_bus,
            transport_path=dbus_path)
        
        # other state
        self._acquired = False
        self._fd = None
        self._read_mtu = None
        self._write_mtu = None

    @property
    def acquired(self):
        return self._acquired

    @property
    def fd(self):
        return self._fd

    @property
    def read_mtu(self):
        return self._read_mtu

    @property
    def write_mtu(self):
        return self._write_mtu

    @property
    def proxy(self):
        """Returns the underlying DBusProxy object. Should only be used for
        property access.
        """
        return self._proxy

    def acquire(self):
        """Acquires the transport OS socket from bluez5.
        """
        if self._acquired:
            return

        logger.debug("Going to acquire OS socket for transport - {}".format(
            self._proxy.path))
        self._fd, self._read_mtu, self._write_mtu = \
            self._proxy.proxy.TryAcquire()
        self._fd = self._fd.take()
        logger.debug("Successfully acquired OS socket - fd={}, readMTU={}, "
            "writeMTU={}".format(self._fd, self._read_mtu, self._write_mtu))
        self._acquired = True

    def __repr__(self):
        return "<MediaTransport: "+self._proxy.path+">"

    def __str__(self):
        return "<MediaTransport: "+self._proxy.path+">"

    def __unicode__(self):
        return "<MediaTransport: "+self._proxy.path+">"

class Profile(dbus.service.Object):
    """Encapsulates a Profile bluez5 object.
    """

    def __init__(self, system_bus, dbus_path):
        super().__init__(self, system_bus, dbus_path)

        self._fds = {} # device: [fd]

        self.on_connect = None
        self.on_disconnect = None
        self.on_release = None

    @dbus.service.method(dbus_interface=Bluez5Utils.PROFILE_INTERFACE,
                         in_signature=None, out_signature=None)
    def Release(self):
        """Called when bluez5 unregisters the profile.
        """
        logger.debug("Bluez5 has unregistered the profile.")
        
        if self.on_release:
            self.on_release()

    @dbus.service.method(dbus_interface=Bluez5Utils.PROFILE_INTERFACE,
                         in_signature="oha{sv}", out_signature=None)
    def NewConnection(self, device, fd, fd_properties):
        """Called when a new service-level connection has been established.
        """
        logger.debug("New service-level connection - device={}, fd={}, fd_"
            "properties={}".format(device, fd, fd_properties))
        fd = fd.take()
        logger.debug("OS-level fd = {}".format(fd))

        # track new socket for later cleanup
        fds = self._fds.get(device, [])
        fds.append(fd)
        self._fds.update({device: fds})
        
        if self.on_connect:
            self.on_connect(
                device=device,
                fd=fd,
                fd_properties=fd_properties)

    @dbus.service.method(dbus_interface=Bluez5Utils.PROFILE_INTERFACE,
                         in_signature=None, out_signature="o")
    def RequestDisconnection(self, device):
        """Called when profile is disconnected from device.
        """
        logger.debug("Profile connections to device {} are now closed.".format(
            device))
        
        # need to close each socket to the device
        for fd in self._fds.pop(device, []):
            try:
                os.close(fd)
            except Exception:
                logger.exception("Unable to close fd {}.".format(fd))
        
        if self.on_disconnect:
            self.on_disconnect(
                device=device)
