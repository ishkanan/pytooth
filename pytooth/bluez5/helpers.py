
import logging

import pydbus

logger = logging.getLogger(__name__)


class Bluez5Utils:
    """Provides some helpful utility functions for interacting with bluez5.
    """

    SERVICE_NAME = "org.bluez"
    OBEX_SERVICE_NAME = "org.bluez.obex"
    ADAPTER_INTERFACE = "org.bluez.Adapter1"
    AGENT_INTERFACE = "org.bluez.Agent1"
    AGENT_MANAGER_INTERFACE = "org.bluez.AgentManager1"
    DEVICE_INTERFACE = "org.bluez.Device1"
    MEDIA_INTERFACE = "org.bluez.Media1"
    MEDIA_ENDPOINT_INTERFACE = "org.bluez.MediaEndpoint1"
    MEDIA_PLAYER_INTERFACE = "org.bluez.MediaPlayer1"
    MEDIA_TRANSPORT_INTERFACE = "org.bluez.MediaTransport1"
    OBEX_CLIENT_INTERFACE = "org.bluez.obex.Client1"
    OBEX_SESSION_INTERFACE = "org.bluez.obex.Session1"
    PHONEBOOK_INTERFACE = "org.bluez.obex.PhonebookAccess1"
    PROFILE_INTERFACE = "org.bluez.Profile1"
    PROFILE_MANAGER_INTERFACE = "org.bluez.ProfileManager1"
    TRANSFER_INTERFACE = "org.bluez.obex.Transfer1"

    OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

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
    def get_managed_objects(bus):
        """Gets all objects that are in the bluez hierarchy.
        """
        return bus.get(Bluez5Utils.SERVICE_NAME, "/") \
            [Bluez5Utils.OBJECT_MANAGER_INTERFACE].GetManagedObjects()

    @staticmethod
    def get_objectmanager(bus):
        return bus.get(Bluez5Utils.SERVICE_NAME, "/") \
            [Bluez5Utils.OBJECT_MANAGER_INTERFACE]

    @staticmethod
    def get_agentmanager(bus):
        return bus.get(Bluez5Utils.SERVICE_NAME, "/org/bluez") \
            [Bluez5Utils.AGENT_MANAGER_INTERFACE]

    @staticmethod
    def get_adapter(bus, adapter_path):
        obj = bus.get(Bluez5Utils.SERVICE_NAME, adapter_path) \
            [Bluez5Utils.ADAPTER_INTERFACE]
        obj.path = adapter_path
        return obj

    @staticmethod
    def get_media(bus, adapter_path):
        obj = bus.get(Bluez5Utils.SERVICE_NAME, adapter_path) \
            [Bluez5Utils.MEDIA_INTERFACE]
        obj.path = adapter_path
        return obj

    @staticmethod
    def get_media_transport(bus, transport_path):
        obj = bus.get(Bluez5Utils.SERVICE_NAME, transport_path) \
            [Bluez5Utils.MEDIA_TRANSPORT_INTERFACE]
        obj.path = transport_path
        return obj

    @staticmethod
    def get_obex_client(bus):
        return bus.get(Bluez5Utils.OBEX_SERVICE_NAME, "/org/bluez/obex") \
            [Bluez5Utils.OBEX_CLIENT_INTERFACE]

    @staticmethod
    def get_obex_session(bus, session_path):
        obj = bus.get(Bluez5Utils.OBEX_SERVICE_NAME, session_path) \
            [Bluez5Utils.OBEX_SESSION_INTERFACE]
        obj.path = session_path
        return obj

    @staticmethod
    def get_phonebook_client(bus, session_path):
        obj = bus.get(Bluez5Utils.OBEX_SERVICE_NAME, session_path) \
            [Bluez5Utils.PHONEBOOK_INTERFACE]
        obj.path = session_path
        return obj

    @staticmethod
    def get_profilemanager(bus):
        return bus.get(Bluez5Utils.SERVICE_NAME, "/org/bluez") \
            [Bluez5Utils.PROFILE_MANAGER_INTERFACE]

    @staticmethod
    def get_transfer(bus, transfer_path):
        obj = bus.get(Bluez5Utils.OBEX_SERVICE_NAME, transfer_path) \
            [Bluez5Utils.TRANSFER_INTERFACE]
        obj.path = transfer_path
        return obj
