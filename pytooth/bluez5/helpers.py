
import logging

import dbus

logger = logging.getLogger("bluez5/"+__name__)


# maps DBus types to Python types (for decode)
_dtop_type_map = {
    dbus.Boolean: bool,
    dbus.Byte: int,
    dbus.Double: float,
    dbus.Int16: int,
    dbus.Int32: int,
    dbus.Int64: int,
    dbus.ObjectPath: str,
    dbus.Signature: str,
    dbus.String: str,
    dbus.UInt16: int,
    dbus.UInt32: int,
    dbus.UInt64: int
}

def dbus_to_py(obj):
    """Helper function that recursively converts a dbus-python object to native
    Python types. If a type is not mapped, it will be returned as-is.
    """
    # container type
    if isinstance(obj, dbus.Array):
        return [dbus_to_py(obj) for obj in obj]
    if isinstance(obj, dbus.ByteArray):
        return bytearray([int(obj) for obj in obj])
    if isinstance(obj, dbus.Dictionary):
        return dict([
            (dbus_to_py(k), dbus_to_py(v)) for k, v in obj.items()])

    # basic type
    if obj.__class__ in _dtop_type_map:
        return _dtop_type_map[obj.__class__](obj)
    return obj

class DBusProxy:
    """Helper class that combines a method proxy object and a property proxy
    object.
    """

    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

    def __init__(self, proxy, path, interface):
        self._interface = interface
        self._path = path
        self._proxy = proxy
        self._props = dbus.Interface(
            proxy,
            DBusProxy.PROPERTIES_INTERFACE)

    @property
    def path(self):
        return self._path

    @property
    def proxy(self):
        return dbus.Interface(self._proxy, self._interface)

    def get(self, name):
        return self._props.Get(self._interface, name)

    def set(self, name, value):
        self._props.Set(self._interface, name, value)

class Bluez5Utils:
    """Provides some helpful utility functions for interacting with bluez5.
    """

    SERVICE_NAME = "org.bluez"
    ADAPTER_INTERFACE = "org.bluez.Adapter1"
    AGENT_INTERFACE = "org.bluez.Agent1"
    AGENT_MANAGER_INTERFACE = "org.bluez.AgentManager1"
    DEVICE_INTERFACE = "org.bluez.Device1"
    MEDIA_INTERFACE = "org.bluez.Media1"
    MEDIA_ENDPOINT_INTERFACE = "org.bluez.MediaEndpoint1"
    MEDIA_PLAYER_INTERFACE = "org.bluez.MediaPlayer1"
    MEDIA_TRANSPORT_INTERFACE = "org.bluez.MediaTransport1"
    PROFILE_INTERFACE = "org.bluez.Profile1"
    PROFILE_MANAGER_INTERFACE = "org.bluez.ProfileManager1"

    OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

    @staticmethod
    def get_managed_objects(bus):
        """Gets all objects that are in the bluez hierarchy.
        """
        return dbus.Interface(
            bus.get_object(Bluez5Utils.SERVICE_NAME, "/"),
            Bluez5Utils.OBJECT_MANAGER_INTERFACE).GetManagedObjects()

    @staticmethod
    def find_adapter(bus, address=None):
        """Finds an adapter with matching address (if present), or None.
        Returns first found adapter if address is None, or None if no adapters
        are present.
        """
        objects = Bluez5Utils.get_managed_objects(bus)
        for path, ifaces in objects.items():
            adapter = ifaces.get(Bluez5Utils.ADAPTER_INTERFACE)
            if adapter is None:
                continue

            if not address or address.upper() == adapter["Address"].upper():
                return Bluez5Utils.get_adapter(
                    bus=bus,
                    adapter_path=path)

        return None

    @staticmethod
    def find_adapter_from_paths(bus, paths, address=None):
        """Finds an adapter with matching address (if present) from the list of
        given adapters, or None. Returns first found adapter if address is None,
        or None if no adapters are present.
        """
        for path in paths:
            obj = Bluez5Utils.get_adapter(
                bus=bus,
                adapter_path=path)
            
            if not address or address.upper() == obj.get("Address").upper():
                return obj

        return None

    @staticmethod
    def get_objectmanager(bus):
        return DBusProxy(
            proxy=bus.get_object(Bluez5Utils.SERVICE_NAME, "/"),
            path="/",
            interface=Bluez5Utils.OBJECT_MANAGER_INTERFACE)

    @staticmethod
    def get_agentmanager(bus):
        return DBusProxy(
            proxy=bus.get_object(Bluez5Utils.SERVICE_NAME, "/org/bluez"),
            path="/org/bluez",
            interface=Bluez5Utils.AGENT_MANAGER_INTERFACE)

    @staticmethod
    def get_adapter(bus, adapter_path):
        return DBusProxy(
            proxy=bus.get_object(Bluez5Utils.SERVICE_NAME, adapter_path),
            path=adapter_path,
            interface=Bluez5Utils.ADAPTER_INTERFACE)

    @staticmethod
    def get_media(bus, adapter_path):
        return DBusProxy(
            proxy=bus.get_object(Bluez5Utils.SERVICE_NAME, adapter_path),
            path=adapter_path,
            interface=Bluez5Utils.MEDIA_INTERFACE)

    @staticmethod
    def get_media_transport(bus, transport_path):
        return DBusProxy(
            proxy=bus.get_object(Bluez5Utils.SERVICE_NAME, transport_path),
            path=transport_path,
            interface=Bluez5Utils.MEDIA_TRANSPORT_INTERFACE)

    @staticmethod
    def get_profilemanager(bus):
        return DBusProxy(
            proxy=bus.get_object(Bluez5Utils.SERVICE_NAME, "/org/bluez"),
            path="/org/bluez",
            interface=Bluez5Utils.PROFILE_MANAGER_INTERFACE)
