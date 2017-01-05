
class Bluez5Utils:
    """Provides some helpful utility functions for interacting with bluez5.
    https://github.com/littlecraft/phony/blob/master/src/phony/bluetooth/adapters/bluez5.py
    """

    SERVICE_NAME = "org.bluez"
    ADAPTER_INTERFACE = "org.bluez.Adapter1"
    AGENT_MANAGER_INTERFACE = "org.bluez.AgentManager1"
    DEVICE_INTERFACE = "org.bluez.Device1"
    MEDIA_INTERFACE = "org.bluez.Media1"
    MEDIA_PLAYER_INTERFACE = "org.bluez.MediaPlayer1"
    MEDIA_TRANSPORT_INTERFACE = "org.bluez.MediaTransport1"
    PROFILE_MANAGER_INTERFACE = "org.bluez.ProfileManager1"

    OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

    @staticmethod
    def get_managed_objects(bus):
        """Gets all objects that are in the bluez hierarchy.
        """
        return bus.get(Bluez5Utils.SERVICE_NAME, "/")[
            Bluez5Utils.OBJECT_MANAGER_INTERFACE].GetManagedObjects()

    @staticmethod
    def find_adapter(bus, address=None):
        """Finds an adapter with matching address (if present), or None.
        Returns first found adapter if address is None, or None if no adapters
        are present.
        """
        objects = Bluez5Utils.get_managed_objects(bus)
        for path, obj in objects.items():
            try:
                adapter = obj[Bluez5Utils.ADAPTER_INTERFACE]
            except KeyError:
                continue
            
            if not address or address.upper() == adapter["Address"].upper():
                return Bluez5Utils.get_adapter_with_props(
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
            obj = Bluez5Utils.get_adapter_with_props(
                bus=bus,
                adapter_path=path)
            
            if not address or address.upper() == obj.Address.upper():
                return obj

        return None

    @staticmethod
    def get_objectmanager(bus):
        o = bus.get(
            Bluez5Utils.SERVICE_NAME,
            "/")[Bluez5Utils.OBJECT_MANAGER_INTERFACE]
        o.path = "/"
        return o

    @staticmethod
    def get_agentmanager(bus):
        o = bus.get(
            Bluez5Utils.SERVICE_NAME,
            "/org/bluez")[Bluez5Utils.AGENT_MANAGER_INTERFACE]
        o.path = "/org/bluez"
        return o

    @staticmethod
    def get_adapter_with_props(bus, adapter_path):
        o = bus.get(
            Bluez5Utils.SERVICE_NAME,
            adapter_path)
        o.path = adapter_path
        return o

    @staticmethod
    def get_media(bus, adapter_path):
        o = bus.get(
            Bluez5Utils.SERVICE_NAME,
            adapter_path)[Bluez5Utils.MEDIA_INTERFACE]
        o.path = adapter_path
        return o

    @staticmethod
    def get_media_transport_with_props(bus, transport_path):
        o = bus.get(
            Bluez5Utils.SERVICE_NAME,
            transport_path)
        o.path = transport_path
        return o

    @staticmethod
    def get_profilemanager(bus):
        o = bus.get(
            Bluez5Utils.SERVICE_NAME,
            "/org/bluez")[Bluez5Utils.PROFILE_MANAGER_INTERFACE]
        o.path = "/org/bluez"
        return o
