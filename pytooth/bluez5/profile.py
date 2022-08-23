import logging
import os
import socket

from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class Profile:
    """Encapsulates a Profile bluez5 object.
    """

    def __init__(self, system_bus, dbus_path):
        self._fds = {} # device: [fd]

        self.on_connect = None
        self.on_disconnect = None
        self.on_release = None

    @property
    def dbus(self):
        return """
        <node>
            <interface name='{}'>
                <method name='Release'>
                </method>
                <method name='NewConnection'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='h' name='fd' direction='in'/>
                    <arg type='a{{sv}}' name='fd_properties' direction='in'/>
                </method>
                <method name='RequestDisconnection'>
                    <arg type='o' name='' direction='out'/>
                </method>
            </interface>
        </node>
        """.format(Bluez5Utils.PROFILE_INTERFACE)

    def Release(self):
        """Called when bluez5 unregisters the profile.
        """
        logger.debug("Bluez5 has unregistered the profile.")

        if self.on_release:
            self.on_release()

    def NewConnection(self, device, fd, fd_properties):
        """Called when a new service-level connection has been established.
        """
        logger.debug("New RFCOMM service-level connection - device={}, fd={}, fd_properties={}".format(
            device, fd, fd_properties))
        fd = os.dup(fd)
        logger.debug("Duplicated fd = {}".format(fd))

        # track new fd for later cleanup
        fds = self._fds.get(device, [])
        fds.append(fd)
        self._fds.update({device: fds})

        if self.on_connect:
            self.on_connect(
                device=device,
                socket=socket.socket(fileno=fd),
                fd_properties=fd_properties)

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
            self.on_disconnect(device=device)
