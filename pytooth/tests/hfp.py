"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.hfp import HandsFreeProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.hfp.pcm import PCMDecoder, PCMEncoder
from pytooth.hfp.sinks import PortAudioSink
from pytooth.hfp.sources import PortAudioSource

logger = logging.getLogger(__name__)


class TestApplication:
    """Test application for the HFP profile. The logic of this code is suitable
    for use in a real-world application.
    """

    def __init__(self, bus, config):
        self.phone = None
        self.sink = None
        self.source = None
        self._socket = None
        self._oncall = False
        self._mtu = None

        # profile setup
        hfp = HandsFreeProfile(
            system_bus=bus,
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
        self.hfp.set_discoverable(enabled=False)
        self.hfp.set_pairable(enabled=False)
        self.hfp.stop()
        self._stop_audio()

    def _adapter_connected_changed(self, adapter, connected):
        # be discoverable if adapter is connected
        self.hfp.set_discoverable(enabled=connected)
        self.hfp.set_pairable(enabled=connected)

    def _audio_connected_changed(self, adapter, connected, socket, mtu, peer):
        # store for later use
        self._socket = socket
        self._mtu = mtu

        # start or stop pumping audio
        if connected:
            self._start_audio()
        else:
            self._stop_audio()

    def _audio_setup_error(self, adapter, status, error):
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
            self.phone = phone
            phone.on_connected_changed = self._phone_connected_changed
            phone.on_event = self._phone_event

    def _profile_status_changed(self, available):
        """Fired when the profile is enabled/disabled at the Bluez5 level. This
        really only occurs if a serious issue with the Bluetooth stack is
        encountered by the OS.
        """
        logger.info("HFP profile is {}avaiable.".format(
            "" if avaiable else "not "))

    def _phone_connected_changed(self, connected):
        """Fired when a connected device has completed initial handshake. The
        properties of 'phone' below are only available after handshake.
        """
        logger.info("Phone remote control connection is {}.".format(
            "established" if connected else "released"))

        if connected:
            logger.info("Phone properties: Codec={}, Features={}, Multi-call={}"
                "".format(
                    self.phone.codec,
                    self.phone.features,
                    self.phone.multicall))

    def _phone_event(self, name, **kwargs):
        """An (a)synchronous phone event occurred.
        """
        logger.info("Received phone event: name=\"{}\", kwargs={}".format(
            name, kwargs))

    def _start_audio(self):
        # audio can start via 2 use cases:
        # - phone makes call
        # - phone receives call

        self.sink = PortAudioSink(
            decoder=PCMDecoder(),
            socket=self._socket,
            read_mtu=self._mtu,
            card_name="pulse",
            buffer_secs=0)
        self.sink.start()
        logger.info("Built new PortAudioSink with PCMDecoder.")

        self.source = PortAudioSource(
            encoder=PCMEncoder(),
            socket=self._socket,
            write_mtu=self._mtu,
            card_name="pulse")
        self.source.start()
        logger.info("Built new PortAudioSource with PCMEncoder.")

    def _stop_audio(self):
        # no more active calls, obviously

        if self.sink:
            self.sink.stop()
            self.sink = None
            logger.info("Destroyed PortAudioSink.")

        if self.source:
            self.source.stop()
            self.source = None
            logger.info("Destroyed PortAudioSource.")
