"""http://www.bluez.org/bluez-5-api-introduction-and-porting-guide/
"""

import logging

from dbus import UInt32

from pytooth.agents import NoInputNoOutputAgent
from pytooth.bluez5.helpers import Bluez5Utils, dbus_to_py
from pytooth.constants import DBUS_AGENT_PATH
from pytooth.errors import CommandError, InvalidOperationError

logger = logging.getLogger(__name__)


class BaseAdapter:
    """Provides functions to control an adapter. Requires subclasses to
    configure an agent. A GI loop is required to receieve DBus signals.
    """

    def __init__(self, system_bus, io_loop, retry_interval, \
        preferred_address=None):
        
        # properties
        self._address = None
        self._connected = False
        self._last_address = None
        self._last_path = None
        self._path = None

        # other
        self._known_adapters = []
        self._preferred_address = preferred_address
        self._started = False
        
        # events
        self.on_connected_changed = None
        self.on_properties_changed = None
        
        # public
        self.io_loop = io_loop
        self.retry_interval = retry_interval

        # dbus / bluez objects
        self._adapter_proxy = None
        self._bus = system_bus
        self._objectmgr_proxy = Bluez5Utils.get_objectmanager(bus=system_bus)

        # subscribe to property changes
        system_bus.add_signal_receiver(
            handler_function=self._propertieschanged,
            signal_name="PropertiesChanged",
            dbus_interface=Bluez5Utils.PROPERTIES_INTERFACE,
            arg0=Bluez5Utils.ADAPTER_INTERFACE,
            path_keyword = "path")

    def start(self):
        """Starts interaction with bluez. If already started, this does nothing.
        """
        if self._started:
            return

        self._started = True
        self.io_loop.add_callback(callback=self._check_adapter_available)
        logger.debug("Checking for '{}' bluetooth adapter...".format(
            self._preferred_address if self._preferred_address \
            else "first available"))

    def stop(self):
        """Stops interaction with bluez. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._known_adapters = []
        self._adapter_proxy = None
        
        if self.connected:
            self._last_address = self._address
            self._address = None
            self._last_path = self._path
            self._path = None
            self._connected = False

    @property
    def address(self):
        """Returns the address of the connected adapter (if any), or None if
        no adapter is connected.
        """
        return self._address

    @property
    def last_address(self):
        """Returns the address of the last connected adapter (if any), or None
        no adapter has ever connected and disconnected.
        """
        return self._last_address

    @property
    def connected(self):
        """Returns True if desired adapter is connected.
        """
        return self._connected

    @property
    def path(self):
        """Returns the DBus object path of the connected adapter (if any), or
        None if no adapter is connected.
        """
        return self._path

    @property
    def last_path(self):
        """Returns the DBus object path of the last connected adapter (if any),
        or None if no adapter has ever connected.
        """
        return self._last_path

    def set_discoverable(self, enabled, timeout=None):
        """Toggles visibility of the BT subsystem to other searching BT devices.
        Timeout is in seconds, or pass None for no timeout.
        """

        if not self._started:
            raise InvalidOperationError("Not started.")
        if self._adapter_proxy is None:
            raise InvalidOperationError("No adapter available.")
            
        try:
            self._adapter_proxy.set("Discoverable", enabled)
            self._adapter_proxy.set("DiscoverableTimeout", UInt32(timeout or 0))
        except Exception as e:
            raise CommandError(e)

    def set_pairable(self, enabled, timeout=None):
        """Makes the BT subsystem pairable with other BT devices. Timeout is
        in seconds, or pass None for no timeout.
        """

        if not self._started:
            raise InvalidOperationError("Not started.")
        if self._adapter_proxy is None:
            raise InvalidOperationError("No adapter available.")

        try:
            self._adapter_proxy.set("Pairable", enabled)
            self._adapter_proxy.set("PairableTimeout", UInt32(timeout or 0))
        except Exception as e:
            raise CommandError(e)

    def _check_adapter_available(self):
        """Attempts to get the specified adapter proxy object. This is called
        repeatedly as it's the most reliable detection method.
        """

        # infinite check loop breakout
        if not self._started:
            return

        try:
            # get first or preferred BT adapter
            if len(self._known_adapters) == 0:
                # this will kick-start the property change signals
                adapter = Bluez5Utils.find_adapter(
                    bus=self._bus,
                    address=self._preferred_address)
            else:
                adapter = Bluez5Utils.find_adapter_from_paths(
                    bus=self._bus,
                    paths=self._known_adapters,
                    address=self._preferred_address)

            # check adapter connection status
            is_found = adapter is not None and self._adapter_proxy is None
            is_lost = adapter is None and self._adapter_proxy is not None
            
            # notify
            if is_lost:
                logger.info("No suitable adapter is available.")
                self._adapter_proxy = None
                self._last_address = self._address
                self._address = None
                self._last_path = self._path
                self._path = None
            elif is_found:
                logger.info("Adapter '{} - {}' is available.".format(
                    adapter.get("Name"),
                    adapter.get("Address")))
                self._adapter_proxy = adapter
                self._address = self._adapter_proxy.get("Address")
                self._path = self._adapter_proxy.path
            if (is_found or is_lost) and self.on_connected_changed:
                self._connected = is_found
                self.io_loop.add_callback(
                    callback=self.on_connected_changed,
                    adapter=self,
                    connected=self.connected)

        except Exception as e:
            logger.exception("Failed to get suitable adapter.")
            
        self.io_loop.call_later(
            delay=self.retry_interval,
            callback=self._check_adapter_available)

    def _propertieschanged(self, interface, changed, invalidated, path):
        """Fired by the system bus subscription when a Bluez5 object property
        changes.
        """
        if not self._started:
            return

        interface = dbus_to_py(interface)
        path = dbus_to_py(path)
        changed = dbus_to_py(changed)
        invalidated = dbus_to_py(invalidated)

        logger.debug("SIGNAL: interface={}, path={}, changed={}, "
            "invalidated={}".format(interface, path, changed, invalidated))

        # make it known to check it later
        if path not in self._known_adapters:
            logger.debug("Remembering adapter {} for later polling.".format(
                path))
            self._known_adapters.append(path)

        # pass changes to event handler if adapter is the one we want to use
        if path == self.path:
            if self.on_properties_changed:
                self.on_properties_changed(
                    adapter=self,
                    props=changed)

class OpenPairableAdapter(BaseAdapter):
    """Adapter that can accept unsecured (i.e. no PIN) pairing requests.
    """

    # multiple profiles must use a single agent
    agent = None
    agentmgr_proxy = None

    def __init__(self, system_bus, io_loop, *args, **kwargs):
        super().__init__(system_bus, io_loop, *args, **kwargs)
        
        self._system_bus = system_bus
        self.io_loop = io_loop

        # build agent if required
        if not OpenPairableAdapter.agent:
            OpenPairableAdapter.agent = NoInputNoOutputAgent(
                system_bus=system_bus,
                dbus_path=DBUS_AGENT_PATH)
        self._agent = OpenPairableAdapter.agent
        self._agent.on_release = self._on_agent_release
        
        # register agent if required
        if not OpenPairableAdapter.agentmgr_proxy:
            OpenPairableAdapter.agentmgr_proxy = Bluez5Utils.get_agentmanager(
                bus=system_bus)
            OpenPairableAdapter.register_agent()

    def register_agent():
        """Class-level method to register the agent.
        """
        OpenPairableAdapter.agentmgr_proxy.proxy.RegisterAgent(
            DBUS_AGENT_PATH,
            "NoInputNoOutput")
        logger.debug("Agent registered.")
        OpenPairableAdapter.agentmgr_proxy.proxy.RequestDefaultAgent(
            DBUS_AGENT_PATH)
        logger.debug("We are now the default agent.")

    def _on_agent_release(self):
        """Called when bluez5 has unregistered the agent.
        """
        logger.debug("Agent was unregistered. Attempting to re-register in 15 "
            "seconds...")
        self.io_loop.call_later(
            delay=15,
            callback=self._register_agent)

    def __repr__(self):
        return "<OpenPairableAdapter: {}>".format(
            self.path if self.connected else self.last_path)

    def __str__(self):
        return self.__repr__()

    def __unicode__(self):
        return self.__repr__()
