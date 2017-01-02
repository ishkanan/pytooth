"""Provides stubs for required callable DBus objects.
https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc
"""

import logging

from gi.repository.GLib import Variant
from pydbus.generic import signal

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
        self._register_context = None
        self._system_bus = system_bus

        self.on_release = None
        self.on_setup_error = None
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
            mt = MediaTransport(transport=Bluez5Utils.get_media_transport(
                bus=self.system_bus,
                transport_path=transport))
        except Exception as ex:
            logger.exception("Error fetching media transport.")
            if self.on_setup_error:
                self.on_setup_error("Error fetching media transport - {}"
                    "".format(ex))
            return

        # hand out
        if self.on_transport_state_changed:
            self.on_transport_state_changed(
                transport=mt,
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
                transport=transport,
                state="released")

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
        if self._acquired:
            raise InvalidOperationError("Already acquired.")
        if self._released:
            raise InvalidOperationError("Already released.")

        logger.debug("Going to acquire OS socket for transport - {}".format(
            self._transport.path))
        self._fd, self._read_mtu, self._write_mtu = self._transport.Acquire()
        logger.debug("Successfully acquired OS socket.")
        self._acquired = True

    def release(self):
        """Releases the transport OS socket. Should be called
        as soon as playback is stopped.
        """
        if not self._acquired:
            raise InvalidOperationError("Not acquired.")
        if self._released:
            raise InvalidOperationError("Already released.")

        logger.debug("Going to release OS socket for transport - {}".format(
            self._transport.path))
        self._transport.Release()
        logger.debug("Successfully released OS socket.")
        self._released = True

    def __repr__(self):
        return self.transport

    def __str__(self):
        return self.transport

    def __unicode__(self):
        return self.transport

