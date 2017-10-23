"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.hfp import HandsFreeProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.hfp.pcm import PCMDecoder, PCMEncoder
from pytooth.hfp.sinks import PortAudioSink
from pytooth.hfp.sources import PortAudioSource

logger = logging.getLogger("hfp-test")


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

        # profile
        hfp = HandsFreeProfile(
            system_bus=bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.instance())
        hfp.on_adapter_connected_changed = self._adapter_connected_changed
        hfp.on_audio_connected = self._audio_connected
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
        if self.sink:
            self.sink.stop()
            self.sink = None
        if self.source:
            self.source.stop()
            self.source = None

    def _adapter_connected_changed(self, adapter, connected):
        # be discoverable if adapter is connected
        self.hfp.set_discoverable(enabled=connected)
        self.hfp.set_pairable(enabled=connected)

    def _audio_connected(self, adapter, socket, mtu, peer):
        # store for later use
        self._socket = socket
        self._mtu = mtu

        # if phone initiated the call, socket is established early
        # if phone received the call, socket establishes later
        if self.phone and self.phone.on_call:
            self._establish_audio()

    def _audio_setup_error(self, adapter, error):
        # error setting up audio link, log and forget
        logger.error("Cannot establish audio link on adapter {} - {}".format(
            adapter, error))

    def _device_connected_changed(self, device, connected, phone):
        logger.info("Device {} has {}connected.".format(
            "" if connected else "not "))

        # keep phone proxy reference if connected
        self.phone = None
        if connected:
            self.phone = phone
            phone.on_indicator_update = self._phone_indicator_update

    def _profile_status_changed(self, available):
        logger.info("HFP profile is {}avaiable.".format(
            "" if avaiable else "not "))

    def _phone_indicator_update(self, data):
        # start sink if a call has been set up
        logger.debug("Got an indicator update!")

        call = data.get("call")

        # if phone initiated the call, socket is established before this indicator
        # if phone received the call, socket establishes after this indicator
        if call == "1":
            self._oncall = True
            if self._socket:
                self._establish_audio()

        # call ended
        elif call == "0":
            self._oncall = False
            self._stop_audio()

    def _establish_audio(self):
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
