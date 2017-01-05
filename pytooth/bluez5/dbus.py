"""Provides stubs for required callable DBus objects.
https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc
"""

import logging
import os

from gi.repository.GLib import Variant

from pytooth.bluez5.helpers import Bluez5Utils
from pytooth.errors import InvalidOperationError

logger = logging.getLogger(__name__)


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
        self._media_proxy.RegisterEndpoint(
            dbus_path,
            {
                "UUID": Variant("s", uuid),
                "Codec": Variant("y", codec),
                "Capabilities": Variant("ay", capabilities)
            })

    def unregister(self, dbus_path):
        """Unregisters our capabilities with bluez5.
        """
        self._media_proxy.UnregisterEndpoint(dbus_path)

class MediaEndpoint:
    """Encapsulates a MediaEndpoint bluez5 object.
    """
    dbus = """
    <node>
      <interface name='org.bluez.MediaEndpoint1'>
        <method name='SetConfiguration'>
          <arg type='o' name='transport' direction='in'/>
          <arg type='a{sv}' name='properties' direction='in'/>
        </method>
        <method name='SelectConfiguration'>
          <arg type='ab' name='capabilities' direction='in'/>
          <arg type='ab' name='response' direction='out'/>
        </method>
        <method name='ClearConfiguration'>
          <arg type='o' name='transport' direction='in'/>
        </method>
        <method name='Release'>
        </method>
      </interface>
    </node>
    """

    def __init__(self, system_bus, configuration):
        self._configuration = configuration # desired
        self._transport = None
        self._register_context = None
        self._system_bus = system_bus

        self.on_release = None
        self.on_transport_setup_error = None
        self.on_transport_state_changed = None

    def register(self, dbus_path):
        """A helper method to register the endpoint on DBus.
        """
        self._register_context = self._system_bus.register_object(
            path=dbus_path,
            object=self,
            node_info=None)

    def unregister(self):
        """A helper method to unregister the endpoint on DBus.
        """
        if self._register_context:
            self._register_context.unregister()
            self._register_context = None

    def SetConfiguration(self, transport, properties):
        """Invoked by bluez5 when the transport configuration has been set.
        """
        logger.debug("Media endpoint config set - {}".format(properties))
        logger.debug("Media transport is available - {}".format(transport))

        # build media transport
        try:
            self._transport = MediaTransport(
                transport=Bluez5Utils.get_media_transport(
                    bus=self._system_bus,
                    transport_path=transport))
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

    def SelectConfiguration(self, capabilities):
        """Invoked by bluez5 when negotiating transport configuration with us.
        """
        logger.debug("Media endpoint capabilities - {}".format(capabilities))
        return self._configuration

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

    def Release(self):
        """Invoked when bluez5 shuts down.
        """
        if self.on_release:
            self.on_release()

class MediaTransport:
    """Encapsulates a bluez5 MediaTransport object.
    """

    def __init__(self, transport):
        self._acquired = False
        self._released = False
        self._transport = transport

        self._fd = None
        self._read_mtu = None
        self._write_mtu = None

    @property
    def acquired(self):
        return self._acquired

    @property
    def released(self):
        return self._released
        
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
    def transport(self):
        """Returns the DBus object. Should only be used to access properties.
        """
        return self._transport

    def acquire(self):
        """Acquires the transport OS socket from bluez5.
        """
        if self._acquired or self._released:
            return

        logger.debug("Going to acquire OS socket for transport - {}".format(
            self._transport.path))
        self._fd, self._read_mtu, self._write_mtu = self._transport.Acquire()
        logger.debug("Successfully acquired OS socket.")
        self._acquired = True

    def release(self):
        """Releases the transport OS socket. Should be called
        as soon as playback is stopped.
        """
        if not self._acquired or self._released:
            return

        logger.debug("Going to release OS socket for transport - {}".format(
            self._transport.path))
        self._transport.Release()
        logger.debug("Successfully released OS socket.")
        self._released = True

    def __repr__(self):
        return "<MediaTransport: "+self._transport.path+">"

    def __str__(self):
        return "<MediaTransport: "+self._transport.path+">"

    def __unicode__(self):
        return "<MediaTransport: "+self._transport.path+">"

class Profile:
    """Encapsulates a Profile bluez5 object.
    """
    dbus = """
    <node>
      <interface name='org.bluez.Profile1'>
        <method name='Release'>
        </method>
        <method name='NewConnection'>
          <arg type='o' name='device' direction='in'/>
          <arg type='h' name='fd' direction='in'/>
          <arg type='a{sv}' name='fd_properties' direction='in'/>
        </method>
        <method name='RequestDisconnection'>
          <arg type='o' name='device' direction='in'/>
        </method>
      </interface>
    </node>
    """

    def __init__(self):
        self._fds = {} # device: [fd]

        self.on_connect = None
        self.on_disconnect = None
        self.on_release = None

    def Release(self):
        """Called when bluez5 unregisters the profile.
        """
        logger.debug("Bluez5 has unregistered the profile.")
        
        if self.on_release:
            self.on_release()

    def NewConnection(self, device, fd, fd_properties):
        """Called when a new service-level connection has been established.
        """
        logger.debug("New service-level connection - device={}, fd={}, fd_"
            "properties={}".format(device, fd, fd_properties))
        
        # track new socket for later cleanup
        fds = self._fds.get(device, [])
        fds.append(fd)
        self._fds.update({device: fds})
        
        if self.on_connect:
            self.on_connect(
                device=device,
                fd=fd,
                fd_properties=fd_properties)

    def RequestDisconnection(self, device):
        """Called when profile is disconnected from device.
        """
        logger.debug("Profile connections to device {} have been closed.".format(
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
