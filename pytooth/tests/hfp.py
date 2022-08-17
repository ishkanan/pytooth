"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

from pytooth.adapters import OpenPairableAdapter
from pytooth.hfp import HandsFreeProfile
from pytooth.hfp.sinks import AlsaAudioSink
from pytooth.hfp.sources import AlsaAudioSource
from pytooth.other.pumps import RealTimeSocketPump

logger = logging.getLogger(__name__)


class TestApplication:
    """Test application for the HFP profile. The logic of this code is suitable
    for use in a real-world application.
    """

    def __init__(self, session_bus, system_bus, config):
        # setup
        self.phone = None
        self._sink = None
        self._source = None
        self._socket_pump = RealTimeSocketPump()
        self._oncall = False
        self._config = config

        # profile setup
        hfp = HandsFreeProfile(
            system_bus=system_bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.current())
        hfp.on_adapter_connected_changed = self._adapter_connected_changed
        hfp.on_audio_connected_changed = self._audio_connected_changed
        hfp.on_audio_setup_error = self._audio_setup_error
        hfp.on_device_connected_changed = self._device_connected_changed
        hfp.on_profile_status_changed = self._profile_status_changed
        self.hfp = hfp

    def start(self):
        # let's go
        self.hfp.start()

    def stop(self):
        # cleanup
        if self.hfp.adapter_connected:
            self.hfp.set_discoverable(enabled=False)
            self.hfp.set_pairable(enabled=False)
        self.hfp.stop()
        self._stop_audio()

    def _adapter_connected_changed(self, adapter, connected):
        logger.debug("Adapter {} is now {}.".format(
            adapter, "connected" if connected else "disconnected"))

        # be discoverable and pairable if adapter is connected
        # note: it is an error to call this if no adapter is avilable
        if connected:
            self.hfp.set_discoverable(enabled=True)
            self.hfp.set_pairable(enabled=True)

    def _audio_connected_changed(self, adapter, connected, socket, mtu, peer):
        """Fired when the remote device establishes an audio connection with
        us.
        """

        # start or stop pumping audio
        if connected:
            self._start_audio(
                socket=socket,
                mtu=mtu)
        else:
            self._stop_audio()

    def _audio_setup_error(self, adapter, error):
        """Fired if an audio link could not be established. This higher-level
        class doesn't have to do anything to cleanup the connection(s) or audio
        paths.
        """
        logger.error("Cannot establish audio link on adapter {} - {}".format(
            adapter, error))

    def _device_connected_changed(self, device, connected, phone):
        """Fired when a device connects but has not completed initial handshake
        with the protocol.
        """
        logger.info("Device {} has {}connected.".format(
            device, "" if connected else "not "))

        # keep phone proxy reference if connected
        self.phone = None
        if connected:
            logger.debug("Peer MAC address = {}".format(phone.peer))
            self.phone = phone
            phone.on_connected_changed = self._phone_connected_changed
            phone.on_event = self._phone_event

    def _profile_status_changed(self, available):
        """Fired when the profile is enabled/disabled at the Bluez5 level. This
        really only occurs if a serious issue with the Bluetooth stack is
        encountered by the OS.
        """
        logger.info("HFP profile is {}avaiable.".format("" if available else "not "))

    def _phone_connected_changed(self, connected):
        """Fired when a connected device has completed initial handshake. The
        properties of 'phone' below are only available after handshake.
        """
        logger.info("Phone remote control connection is {}.".format(
            "established" if connected else "released"))

        if connected:
            logger.info("Phone properties: Codec={}, Features={}, Multi-call={}".format(
                self.phone.codec,
                self.phone.features,
                self.phone.multicall))

    def _phone_event(self, name, **kwargs):
        """An (a)synchronous phone event occurred.
        """
        logger.info("Received phone event: name=\"{}\", kwargs={}".format(
            name, kwargs))

    def _start_audio(self, socket, mtu):
        # audio can start via 2 use cases:
        # - phone makes call
        # - phone receives call

        self._sink = AlsaAudioSink(
            socket_pump=self._socket_pump,
            device_name=self._config["alsasink"])
        self._sink.start()
        logger.info("Built new AlsaAudioSink.")

        self._source = AlsaAudioSource(
            socket_pump=self._socket_pump,
            mtu=mtu,
            device_name=self._config["alsasource"])
        self._source.start()
        logger.info("Built new AlsaAudioSource.")

        self._socket_pump.start(
            socket=socket,
            read_mtu=mtu,
            write_mtu=mtu,
            nodata_wait_msecs=100)
        logger.info("Started the socket pump.")

    def _stop_audio(self):
        # no more active calls, obviously

        if self._sink:
            self._sink.stop()
            self._sink = None
            logger.info("Destroyed AlsaAudioSink.")

        if self._source:
            self._source.stop()
            self._source = None
            logger.info("Destroyed AlsaAudioSource.")

        if self._socket_pump.started:
            self._socket_pump.stop()
            logger.info("Stopped the socket pump.")
