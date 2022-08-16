"""http://www.bluez.org/bluez-5-api-introduction-and-porting-guide/
"""

from functools import partial
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
        """Starts interaction with Bluez. If already started, this does nothing.
        """
        if self._started:
            return

        self._started = True
        self.io_loop.add_callback(callback=self._find_suitable_adapter)
        if self._preferred_address:
            logger.debug("Checking for adapter with address '{}'...".format(
                self._preferred_address))
        else:
            logger.debug("Checking for first available adapter...")

    def stop(self):
        """Stops interaction with Bluez. If already stopped, this does nothing.
        """
        if not self._started:
            return

        self._started = False
        self._adapter_proxy = None
        if self.connected:
            self._address = None
            self._connected = False
            self._last_address = self._address
            self._last_path = self._path
            self._path = None

    @property
    def address(self):
        """Returns the address of the connected adapter, or None if no adapter
        is connected.
        """
        return self._address

    @property
    def connected(self):
        """Returns True if a suitable adapter has been found and is connected,
        False otherwise.
        """
        return self._connected

    @property
    def last_address(self):
        """Returns the address of the last suitable adapter, or None if no
        adapter has ever been found and formerly connected.
        """
        return self._last_address

    @property
    def last_path(self):
        """Returns the DBus object path of the last connected adapter, or None
        if no adapter has ever connected.
        """
        return self._last_path

    @property
    def path(self):
        """Returns the DBus object path of the current suitable and connected
        adapter, or None if no adapter is connected.
        """
        return self._path

    def set_discoverable(self, enabled, timeout=None):
        """Toggles visibility of the BT subsystem to other searching BT devices.
        Timeout is in seconds, or pass None for no timeout.
        """

        if not self._started:
            raise InvalidOperationError("Not started.")
        if not self._connected:
            raise InvalidOperationError("No suitable adapter available.")
            
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
        if not self._connected:
            raise InvalidOperationError("No suitable adapter available.")

        try:
            self._adapter_proxy.set("Pairable", enabled)
            self._adapter_proxy.set("PairableTimeout", UInt32(timeout or 0))
        except Exception as e:
            raise CommandError(e)

    def _find_suitable_adapter(self):
        """Searches for a suitable adapter based on preferred address or
        'best available'. Executes repeatedly until an adapter is found.
        This is initiated on start() and on power status change.
        """
        if not self._started:
            return

        try:
            # get either:
            # 1) first available adapter, or
            # 2) specific adapter based on preferred address
            # note: this will start the property change signals
            adapter = Bluez5Utils.find_adapter(
                bus=self._bus,
                address=self._preferred_address)

            if adapter is None:
                logger.info("No suitable adapter is available.")
            else:
                logger.info("Found suitable adapter - name={}, address={}".format(
                    adapter.get("Name"),
                    adapter.get("Address")))
                self._adapter_proxy = adapter
                self._address = self._adapter_proxy.get("Address")
                # we have to assume this as Bluez does not alert us if the
                # adapter has power before we started this library
                self._connected = self._adapter_proxy.get("Powered")
                self._path = self._adapter_proxy.path
                self.io_loop.add_callback(
                    callback=self.on_connected_changed,
                    adapter=self,
                    connected=self.connected)

        except Exception as e:
            logger.exception("Failed to get suitable adapter.")
        
        # try again if no suitable adapter was found
        if not self._connected:
            self.io_loop.call_later(
                delay=self.retry_interval,
                callback=self._find_suitable_adapter)

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

        # is it the adapter we have found suitable?
        if path == self.path:
            # alert to property changes
            if self.on_properties_changed:
                self.io_loop.add_callback(partial(
                    self.on_properties_changed,
                    adapter=self,
                    props=changed))

            # react if adapter was powered off (i.e. disconnected)
            if "Powered" in changed and not changed["Powered"]:
                self._adapter_proxy = None
                self._connected = False
                self._last_address = self._address
                self._address = None
                self._last_path = self._path
                self._path = None
                self.io_loop.add_callback(
                    callback=self.on_connected_changed,
                    adapter=self,
                    connected=False)
                self.io_loop.add_callback(callback=self._find_suitable_adapter)

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
