import logging

from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class ObexSessionFactory:
    """Uses an Obex.Client1 bluez5 object to create and destroy Obex sessions.
    This does not do any session tracking; it is up to the caller to invoke
    destroy_session for every active session.
    """

    def __init__(self, session_bus):
        self._obex_client_proxy = Bluez5Utils.get_obex_client(bus=session_bus)
        self._session_bus = session_bus

    def create_session(self, destination, target):
        """Creates and returns a new Obex client session, encapsulated in a
        pytooth.bluez5.helpers.DBusProxy object.
        """
        session_path = self._obex_client_proxy.CreateSession(
            destination,
            {
                "Target": target
            })
        return Bluez5Utils.get_obex_session(
            bus=self._session_bus,
            session_path=session_path)

    def destroy_session(self, session_path):
        """Closes an existing Obex session.
        """
        self._obex_client_proxy.RemoveSession(session_path)
