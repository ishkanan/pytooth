"""http://www.bluez.org/bluez-5-api-introduction-and-porting-guide/
"""

from functools import partial
import logging
from unittest.mock import MagicMock

from pytooth.errors import CommandError, InvalidOperationError
from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class BaseAdapter:
    """Provides functions to control an adapter. Requires subclasses to
    configure an agent. A GI loop is required to receieve DBus signals.
    """

    def __init__(self, system_bus, io_loop, retry_interval, \
        adapter_address=None):
        
        # subclass-accessible
        self._adapter_address = adapter_address
        self._started = False
        
        # events
        self.on_connected_changed = None
        self.on_properties_changed = None
        
        # public
        self.io_loop = io_loop
        self.retry_interval = retry_interval

        # dbus / bluez objects
        self._adapter_proxy = None
        self._adapter_props_proxy = None
        self._bus = system_bus
        self._objectmgr_proxy = Bluez5Utils.get_objectmanager(bus=system_bus)

        # subscribe to property changes
        system_bus.subscribe(
            iface=Bluez5Utils.PROPERTIES_INTERFACE,
            signal="PropertiesChanged",
            arg0=Bluez5Utils.ADAPTER_INTERFACE,
            signal_fired=self._propertieschanged)

    def start(self):
        """Starts interaction with bluez. If already started, this does nothing.
        """
        if self._started:
            return

        self._started = True
        self.io_loop.add_callback(callback=self._check_adapter_available)

    def stop(self):
        """Stops interaction with bluez. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._adapter_proxy = None
        self._adapter_props_proxy = None

    def set_discoverable(self, enabled, timeout=None):
        """Toggles visibility of the BT subsystem to other searching BT devices.
        Timeout is in seconds, or pass None for no timeout.
        """

        if not self._started:
            raise InvalidOperationError("Not started.")
        if self._adapter_props_proxy is None:
            raise InvalidOperationError("Adapter not available.")
            
        try:
            self._adapter_props_proxy.Discoverable = enabled
            self._adapter_props_proxy.DiscoverableTimeout = timeout or 0
        except Exception as e:
            raise CommandError(e)

    def set_pairable(self, enabled, timeout=None):
        """Makes the BT subsystem pairable with other BT devices. Timeout is
        in seconds, or pass None for no timeout.
        """

        if not self._started:
            raise InvalidOperationError("Not started.")
        if self._adapter_props_proxy is None:
            raise InvalidOperationError("Adapter not available.")

        try:
            self._adapter_props_proxy.Pairable = enabled
            self._adapter_props_proxy.PairableTimeout = timeout or 0
        except Exception as e:
            raise CommandError(e)

    def _check_adapter_available(self):
        """Attempts to get the specified adapter proxy object. This is called
        repeatedly as there's no way to be notified by DBus of adapter
        connection/disconnection.
        """

        # break out of potentially infinite check loop
        if not self._started:
            return

        try:
            # get first or preferred BT adapter
            logger.debug("Checking for '{}' bluetooth adapter...".format(
                self._adapter_address if self._adapter_address \
                else "first available"))
            adapter = Bluez5Utils.find_adapter(
                bus=self._bus,
                address=self._adapter_address)

            # notify if state changed since last check
            s1 = adapter is None and self._adapter_proxy is not None
            s2 = adapter is not None and self._adapter_proxy is None
            adapter = adapter or MagicMock(Name=None, Address=None)
            logger.info("BT adapter '{} - {}' is{} available.".format(
                adapter.Name,
                adapter.Address,
                "" if adapter.Address else " not"))
            if s1 or s2:
                self._adapter_proxy = adapter[Bluez5Utils.ADAPTER_INTERFACE]
                self._adapter_props_proxy = adapter if adapter.Address else None
                if self.on_connected_changed is not None:
                    self.io_loop.add_callback(
                        callback=partial(
                            self.on_connected_changed,
                            connected=s2))

        except Exception as e:
            logger.exception("Failed to get BT adapter.")
            
        self.io_loop.call_later(
            delay=self.retry_interval,
            callback=self._check_adapter_available)

    def _propertieschanged(self, sender, object, iface, signal, params):
        """Fired by the system bus subscription when a Bluez5 object property
        changes. 
        e.g.
            object=/org/bluez/hci0/dev_BC_F5_AC_81_D0_9E
            iface=org.freedesktop.DBus.Properties
            signal=PropertiesChanged
            params=('org.bluez.Device1', {'Connected': True}, [])
        """
        if not self._started:
            return
        if params[0] != Bluez5Utils.ADAPTER_INTERFACE:
            return
        
        logger.debug("SIGNAL: object={}, iface={}, signal={}, params={}".format(
            object, iface, signal, params))

        if self.on_properties_changed is not None:
            self.on_properties_changed(
                props=params[1])


class OpenPairableAdapter(BaseAdapter):
    """Adapter that can accept unsecured (i.e. no PIN) pairing requests.
    """

    def __init__(self, system_bus, io_loop, retry_interval, \
        adapter_address=None):
        super().__init__(system_bus, io_loop, retry_interval, \
            adapter_address)
        
        # disable requirement for PIN when pairing
        self._agentmgr_proxy = Bluez5Utils.get_agentmanager(bus=system_bus)
        self._agentmgr_proxy.RegisterAgent("/org/bluez", "NoInputNoOutput")

