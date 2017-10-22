"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.hfp import HandsFreeProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.audio.decoders.pcm import PCMDecoder
from pytooth.audio.sinks.playback import PortAudioSink

logger = logging.getLogger("hfp-test")


class TestApplication:
    """Test application for the HFP profile.
    """

    def __init__(self, bus, config):
        self.sink = None
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
        if self._oncall:
            self._make_sink()

    def _audio_setup_error(self, adapter, error):
        pass

    def _device_connected_changed(self, device, connected, phone):
        self.phone = phone
        phone.on_indicator_update = self._phone_indicator_update

    def _profile_status_changed(self, available):
        pass

    def _phone_indicator_update(self, data):
        # start sink if a call has been set up
        logger.debug("Got an indicator update!")

        call = data.get("call")

        # if phone initiated the call, socket is established before this indicator
        # if phone received the call, socket establishes after this indicator
        if call == "1":
            self._oncall = True
            if self._socket:
                self._make_sink()
                self.sink.start()

        # call ended
        elif call == "0" and self.sink:
            self._oncall = False
            self.sink.stop()
            self.sink = None
            logger.info("Destroyed sink.")

    def _make_sink(self):
        # sinks can be made via 2 use cases:
        # - phone makes call
        # - phone receives call

        # self.sink = DirectFileSink(
        #     socket_or_fd=self._socket,
        #     filename="/home/ishkanan/out.cvsd")
        # self.sink.start()

        self.sink = PortAudioSink(
            decoder=PCMDecoder(),
            socket_or_fd=self._socket,
            read_mtu=self._mtu,
            card_name="pulse",
            buffer_secs=0)

        # self.sink = WAVFileSink(
        #     decoder=SoxDecoder(
        #         codec="cvsd",
        #         out_channels=1,
        #         out_samplerate=8000,
        #         out_samplesize=8), # bits
        #     socket_or_fd=self._socket,
        #     read_mtu=self._mtu,
        #     filename="/home/vagrant/pytooth/out.wav")

        logger.info("Built new sink.")
