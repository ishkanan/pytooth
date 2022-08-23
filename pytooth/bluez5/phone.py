import logging
import os

from pytooth.bluez5.helpers import Bluez5Utils

logger = logging.getLogger(__name__)


class PhonebookClient:
    """Wrapper that provides access to PBAP client methods. This class only
    permits one transfer of phonebook data at a time. As per PBAP spec, this
    also provides access to call history datasets.

    https://github.com/r10r/bluez/blob/master/doc/obex-api.txt
    """
    def __init__(self, session_bus, session):
        self._client = Bluez5Utils.get_phonebook_client(
            bus=session_bus,
            session_path=session.path)
        self._destination = session.Destination
        self._session = session
        self._session_bus = session_bus
        self._transfer = None
        self._transfer_file = None

        # for some reason we can't access the properties via the DBusProxy
        # object. quite strange...
        # session_bus.add_signal_receiver(
        #     self._properties_changed,
        #     dbus_interface=Bluez5Utils.PROPERTIES_INTERFACE,
        #     signal_name="PropertiesChanged",
        #     path_keyword="path")
        self._props_changed_subscription = session.PropertiesChanged.connect(
            self._properties_changed)

        # public events
        self.on_transfer_complete = None
        self.on_transfer_error = None

    @property
    def destination(self):
        return self._destination

    @property
    def session(self):
        return self._session

    def _properties_changed(self, interface, properties, invalidated, path):
        """DBus callback that we use for checking the status of an existing
        transfer.
        """
        if self._transfer is None:
            return
        if self._transfer.path != path:
            return
        if "Status" not in properties:
            return

        status = properties["Status"]

        # still going?
        if status in ["queued", "active"]:
            return

        # store and cleanup before anything can blow up
        self._transfer = None
        fname = self._transfer_file
        self._transfer_file = None

        # Bluez doesn't elaborate on the error :(
        if status == "error":
            logger.info("Obex session transfer from '{}' failed.".format(
                self._destination))
            if self.on_transfer_error:
                self.on_transfer_error(client=self)

        # Bluez writes the data to a temp file so we need
        # to return all data in that file and delete it
        # NOTE: parsing is the initiators responsibility
        if status == "complete":
            logger.info("Obex session transfer from '{}' completed.".format(
                self._destination))
            data = None
            try:
                with open(fname, 'r') as f:
                    data = f.read()
            except Exception:
                logger.exception("Error reading transferred data in temporary file '{}' from '{}'.".format(
                    fname,
                    self._destination))
                if self.on_transfer_error:
                    self.on_transfer_error(client=self)
            else:
                if self.on_transfer_complete:
                    self.on_transfer_complete(
                        client=self,
                        data=data)

            # delete the temporary file
            try:
                os.remove(fname)
                logger.debug("Temp destination file '{}' for transfer from '{}' has been deleted.".format(
                    fname,
                    self._destination))
            except Exception as e:
                logger.warning("Error deleting temp destination file '{}' for transfer from '{}' - {}".format(
                    fname,
                    self._destination,
                    e))

    def select(self, location, name):
        """Selects a phonebook for further operations. Location can be ['int',
        'sim1', 'sim2'...] and name can be ['pb', 'ich', 'och', 'mch', 'cch'].
        This does nothing if a transfer is in progress.
        """
        if self._transfer is not None:
            return

        self._client.Select(location, name)

    def get_all(self, fmt=None, order=None, offset=None, maxcount=None, \
        fields=None):
        """Fetches the entire selected phonebook. Actual data is returned via
        the `on_transfer_complete` event, if the transfer is successful. This
        does nothing if a transfer is in progress.
        """
        if self._transfer is not None:
            return

        # all filters are optional
        filters = {}
        if fmt is not None:
            filters.update({"Format": fmt})
        if order is not None:
            filters.update({"Order": order})
        if offset is not None:
            filters.update({"Offset": offset})
        if maxcount is not None:
            filters.update({"MaxCount": maxcount})
        if fields is not None:
            filters.update({"Fields": fields})

        # start the transfer
        tx_path, tx_props = self._client.PullAll("", filters)
        self._transfer = Bluez5Utils.get_transfer(
            bus=self._session_bus,
            transfer_path=tx_path)
        self._transfer_file = tx_props["Filename"]

    def abort(self):
        """Abort the active transfer, if any. The underlying Obex session is
        left as-is. If there is no active transfer, this does nothing.
        """
        if self._transfer is not None:
            self._transfer = None
            self._transfer_file = None
