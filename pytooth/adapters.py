"""http://www.bluez.org/bluez-5-api-introduction-and-porting-guide/
"""

import logging

from pytooth.errors import CommandError, InvalidOperationError
from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class BaseAdapter:
    """Provides functions to control an adapter. Requires subclasses to
    configure an agent. A GI loop is required to receieve DBus signals.
    """

    def __init__(self, system_bus, io_loop, retry_interval, \
        preferred_address=None):
        
        # subclass-accessible
        self._preferred_address = preferred_address
        self._connected = False
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
        self._connected = False
        self._adapter_proxy = None
        self._adapter_props_proxy = None

    @property
    def address(self):
        """Returns the address of the connected adapter (if any), or None if
        no adapter is connected.
        """
        if self._adapter_props_proxy:
            return self._adapter_props_proxy.Address
        return None

    @property
    def connected(self):
        return self._connected

    @property
    def dbus_path(self):
        """Returns the DBus object path of the connected adapter (if any), or
        None if no adapter is connected.
        """
        if self._adapter_props_proxy:
            help(self._adapter_props_proxy)
            return self._adapter_props_proxy.Path
        return None

    def set_discoverable(self, enabled, timeout=None):
        """Toggles visibility of the BT subsystem to other searching BT devices.
        Timeout is in seconds, or pass None for no timeout.
        """

        if not self._started:
            raise InvalidOperationError("Not started.")
        if self._adapter_props_proxy is None:
            raise InvalidOperationError("No adapter available.")
            
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
            raise InvalidOperationError("No adapter available.")

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
                self._preferred_address if self._preferred_address \
                else "first available"))
            adapter = Bluez5Utils.find_adapter(
                bus=self._bus,
                address=self._preferred_address)

            # check adapter connection status
            is_found = adapter is not None and self._adapter_proxy is None
            is_lost = adapter is None and self._adapter_proxy is not None
            
            # notify
            if is_lost:
                logger.info("No suitable adapter is available.")
                self._adapter_proxy = None
                self._adapter_props_proxy = None
            if is_found:
                logger.info("Adapter '{} - {}' is available.".format(
                    adapter.Name,
                    adapter.Address))
                self._adapter_proxy = adapter[Bluez5Utils.ADAPTER_INTERFACE]
                self._adapter_props_proxy = adapter
            if (is_found or is_lost) and self.on_connected_changed is not None:
                self._connected = is_found
                self.io_loop.add_callback(
                    callback=self.on_connected_changed,
                    adapter=self)

        except Exception as e:
            logger.exception("Failed to get suitable adapter.")
            
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
        if object != self.dbus_path:
            return

        logger.debug("SIGNAL: object={}, iface={}, signal={}, params={}".format(
            object, iface, signal, params))

        if self.on_properties_changed is not None:
            self.on_properties_changed(
                adapter=self,
                props=params[1])


class OpenPairableAdapter(BaseAdapter):
    """Adapter that can accept unsecured (i.e. no PIN) pairing requests.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # disable requirement for PIN when pairing
        self._agentmgr_proxy = Bluez5Utils.get_agentmanager(
            bus=kwargs["system_bus"])
        self._agentmgr_proxy.RegisterAgent("/org/bluez", "NoInputNoOutput")

