"""https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/agent-api.txt
"""

import logging

import dbus.service

from pytooth.bluez5.helpers import Bluez5Utils, to_python_types

logger = logging.getLogger(__name__)


class NoInputNoOutputAgent(dbus.service.Object):
    """Provides agents to control an adapter. Requires subclasses to
    configure an agent. A GI loop is required to receieve DBus signals.
    """

    def __init__(self, system_bus, dbus_path):
        dbus.service.Object.__init__(self, system_bus, dbus_path)

        self.on_release = None

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature=None, out_signature=None)
    def Release(self):
        logger.debug("NINO: Released.")
        if self.on_release:
            self.on_release()

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="os", out_signature=None)
    def AuthorizeService(self, device, uuid):
        logger.debug("NINO: AuthorizeService {}, {}".format(device, uuid))

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logger.debug("NINO: RequestPinCode {}".format(device))
        return "0000"

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logger.debug("NINO: RequestPasskey {}".format(device))
        return 0000

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="ouq", out_signature=None)
    def DisplayPasskey(self, device, passkey, entered):
        logger.debug("NINO: DisplayPasskey {}, {} entered {})".format(
            device, passkey, entered))

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="os", out_signature=None)
    def DisplayPinCode(self, device, pincode):
        logger.debug("NINO: DisplayPinCode {}, {}".format(device, pincode))

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="ou", out_signature=None)
    def RequestConfirmation(self, device, passkey):
        logger.debug("NINO: RequestConfirmation {}, {}".format(device, passkey))

    @to_python_types
    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="o", out_signature=None)
    def RequestAuthorization(self, device):
        logger.debug("NINO: RequestAuthorization {}".format(device))

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature=None, out_signature=None)
    def Cancel(self):
        logger.debug("NINO: Cancelled.")
