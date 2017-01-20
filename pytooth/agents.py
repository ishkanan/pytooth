"""https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/agent-api.txt
"""

import logging

import dbus.service

from pytooth.bluez5.helpers import Bluez5Utils, dbus_to_py

logger = logging.getLogger(__name__)


class NoInputNoOutputAgent(dbus.service.Object):
    """Provides agents to control an adapter. Requires subclasses to
    configure an agent. A GI loop is required to receieve DBus signals.
    """

    def __init__(self, system_bus, dbus_path):
        dbus.service.Object.__init__(self, system_bus, dbus_path)

        self.on_release = None

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature=None, out_signature=None)
    def Release(self):
        logger.debug("NINO: Released.")
        if self.on_release:
            self.on_release()

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="os", out_signature=None)
    def AuthorizeService(self, device, uuid):
        device = dbus_to_py(device)
        uuid = dbus_to_py(uuid)

        logger.debug("NINO: AuthorizeService {}, {}".format(device, uuid))

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        device = dbus_to_py(device)

        logger.debug("NINO: RequestPinCode {}".format(device))
        return "0000"

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        device = dbus_to_py(device)

        logger.debug("NINO: RequestPasskey {}".format(device))
        return 0000

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="ouq", out_signature=None)
    def DisplayPasskey(self, device, passkey, entered):
        device = dbus_to_py(device)
        passkey = dbus_to_py(passkey)
        entered = dbus_to_py(entered)

        logger.debug("NINO: DisplayPasskey {}, {} entered {})".format(
            device, passkey, entered))

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="os", out_signature=None)
    def DisplayPinCode(self, device, pincode):
        device = dbus_to_py(device)
        pincode = dbus_to_py(pincode)

        logger.debug("NINO: DisplayPinCode {}, {}".format(device, pincode))

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="ou", out_signature=None)
    def RequestConfirmation(self, device, passkey):
        device = dbus_to_py(device)
        passkey = dbus_to_py(passkey)

        logger.debug("NINO: RequestConfirmation {}, {}".format(device, passkey))

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature="o", out_signature=None)
    def RequestAuthorization(self, device):
        device = dbus_to_py(device)

        logger.debug("NINO: RequestAuthorization {}".format(device))

    @dbus.service.method(dbus_interface=Bluez5Utils.AGENT_INTERFACE,
                         in_signature=None, out_signature=None)
    def Cancel(self):
        logger.debug("NINO: Cancelled.")
