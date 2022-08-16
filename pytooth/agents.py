"""https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/agent-api.txt
"""

import logging

from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class NoInputNoOutputAgent:
    """Provides agents to control an adapter. Requires subclasses to
    configure an agent. A GI loop is required to receieve DBus signals.
    """

    dbus = """
        <node>
            <interface name='{}'>
                <method name='Release'>
                </method>
                <method name='AuthorizeService'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='s' name='uuid' direction='in'/>
                </method>
                <method name='RequestPinCode'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='s' name='' direction='out'/>
                </method>
                <method name='RequestPasskey'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='u' name='' direction='out'/>
                </method>
                <method name='DisplayPasskey'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='u' name='passkey' direction='in'/>
                    <arg type='q' name='entered' direction='in'/>
                </method>
                <method name='DisplayPinCode'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='s' name='pincode' direction='in'/>
                </method>
                <method name='RequestConfirmation'>
                    <arg type='o' name='device' direction='in'/>
                    <arg type='u' name='passkey' direction='in'/>
                </method>
                <method name='RequestAuthorization'>
                    <arg type='o' name='device' direction='in'/>
                </method>
                <method name='Cancel'>
                </method>
            </interface>
        </node>""".format(Bluez5Utils.AGENT_INTERFACE)

    def __init__(self):
        self.on_release = None

    def Release(self):
        logger.debug("NINO: Released.")
        if self.on_release:
            self.on_release()

    def AuthorizeService(self, device, uuid):
        logger.debug("NINO: AuthorizeService {}, {}".format(device, uuid))

    def RequestPinCode(self, device):
        logger.debug("NINO: RequestPinCode {}".format(device))
        return "0000"

    def RequestPasskey(self, device):
        logger.debug("NINO: RequestPasskey {}".format(device))
        return 0000

    def DisplayPasskey(self, device, passkey, entered):
        logger.debug("NINO: DisplayPasskey {}, {} entered {})".format(
            device, passkey, entered))

    def DisplayPinCode(self, device, pincode):
        logger.debug("NINO: DisplayPinCode {}, {}".format(device, pincode))

    def RequestConfirmation(self, device, passkey):
        logger.debug(
            "NINO: RequestConfirmation {}, {}".format(device, passkey))

    def RequestAuthorization(self, device):
        logger.debug("NINO: RequestAuthorization {}".format(device))

    def Cancel(self):
        logger.debug("NINO: Cancelled.")
