import logging
import os
import socket

from .helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class Media:
    """Encapsulates a Media bluez5 object.
    """

    def __init__(self, system_bus, adapter_path):
        self._media_proxy = Bluez5Utils.get_media(
            bus=system_bus,
            adapter_path=adapter_path)

    def register(self, endpoint_path, uuid, codec, capabilities):
        """Registers our capabilities with bluez5.
        """
        self._media_proxy.RegisterEndpoint(
            endpoint_path,
            {
                "UUID": uuid,
                "Codec": codec,
                "Capabilities": capabilities
            })

    def unregister(self, dbus_path):
        """Unregisters our capabilities with bluez5.
        """
        self._media_proxy.UnregisterEndpoint(dbus_path)


class MediaEndpoint:
    """Implements a MediaEndpoint bluez5 interface.
    """

    def __init__(self, system_bus, configuration):
        self._configuration = configuration # desired
        self._transport = None
        self._system_bus = system_bus

        self.on_release = None
        self.on_transport_setup_error = None
        self.on_transport_state_changed = None

    @property
    def dbus(self):
        return """
        <node>
            <interface name='{}'>
                <method name='SetConfiguration'>
                    <arg type='o' name='transport' direction='in'/>
                    <arg type='a{sv}' name='properties' direction='in'/>
                </method>
                <method name='SelectConfiguration'>
                    <arg type='ab' name='capabilities' direction='in'/>
                    <arg type='ab' name='' direction='out'/>
                </method>
                <method name='ClearConfiguration'>
                    <arg type='o' name='transport' direction='in'/>
                </method>
                <method name='Release'>
                </method>
            </interface>
        </node>
        """.format(Bluez5Utils.MEDIA_ENDPOINT_INTERFACE)

    def SetConfiguration(self, transport, properties):
        """Invoked by bluez5 when the transport configuration has been set.
        """
        logger.debug("Media endpoint config set - {}".format(properties))
        logger.debug("Media transport is available - {}".format(transport))

        try:
            self._transport = MediaTransport(
                system_bus=self._system_bus,
                dbus_path=transport)
        except Exception as ex:
            logger.exception("Error fetching media transport.")
            if self.on_transport_setup_error:
                self.on_transport_setup_error(ex)
            return

        if self.on_transport_state_changed:
            self.on_transport_state_changed(
                transport=self._transport,
                available=True)

    def SelectConfiguration(self, capabilities):
        """Invoked by bluez5 when negotiating transport configuration with us.
        """
        logger.debug("Media endpoint capabilities - {}".format(capabilities))
        return self._configuration

    def ClearConfiguration(self, transport):
        """Invoked by bluez5 when it is forgetting configuration because the
        transport was stopped.
        """
        logger.debug("Bluez5 has cleared the configuration for transport - {}".format(
            transport))

        if self.on_transport_state_changed:
            self.on_transport_state_changed(
                transport=self._transport,
                available=False)
            self._transport = None

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
        self._socket = None
        self._read_mtu = None
        self._write_mtu = None
        self._dbus_path = dbus_path

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
    def socket(self):
        return self._socket

    @property
    def proxy(self):
        """Returns the underlying DBusProxy object. Should only be used for
        property access.
        """
        return self._proxy

    def acquire(self):
        """Acquires the transport OS file descriptor from bluez5.
        """
        if self._acquired:
            return

        logger.debug("Acquiring OS file descriptor for transport {}".format(
            self._dbus_path))
        self._fd, self._read_mtu, self._write_mtu = self._proxy.TryAcquire()
        self._fd = os.dup(self._fd) # effectively a "take()" call
        self._socket = socket.socket(fileno=self._fd)
        logger.debug("Acquired OS file descriptor - fd={}, readMTU={}, writeMTU={}".format(
            self._fd, self._read_mtu, self._write_mtu))
        self._acquired = True

    def release(self):
        """Manually releases the media transport.
        """
        if not self._acquired:
            return

        logger.debug("Releasing the media transport.")
        self._proxy.Release()
        self._acquired = False

    def __repr__(self):
        return "<MediaTransport: {}>".format(self._dbus_path)

    def __str__(self):
        return "<MediaTransport: {}>".format(self._dbus_path)

    def __unicode__(self):
        return "<MediaTransport: {}>".format(self._dbus_path)

