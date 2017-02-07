"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.hfp import HandsFreeProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.audio.decoders.sbc import SBCDecoder
from pytooth.audio.decoders.sox import SoxDecoder
from pytooth.audio.sinks import DirectFileSink, PortAudioSink, WAVFileSink

logger = logging.getLogger("hfp-test")


class TestApplication:
    """Test application for the HFP profile.
    """

    def __init__(self, config):
        # init
        bus = pytooth.init()
        
        self.sink = None

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

        # self.sink = PortAudioSink(
        #     decoder=SBCDecoder(
        #         libsbc_so_file="/usr/local/lib/libsbc.so.1.2.0"),
        #     socket_or_fd=socket,
        #     read_mtu=mtu,
        #     card_name="pulse")

        # self.sink = WAVFileSink(
        #     decoder=SoxDecoder(
        #         codec="cvsd",
        #         out_channels=1,
        #         out_samplerate=8000,
        #         out_samplesize=8), # bits
        #     socket_or_fd=socket,
        #     read_mtu=mtu,
        #     filename="/home/vagrant/pytooth/out.wav")
        pass

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
        if call == "1":
            self.sink = DirectFileSink(
                socket_or_fd=self._socket,
                filename="/home/vagrant/pytooth/out.cvsd")
            self.sink.start()
            logger.info("Built new sink.")
        elif call == "0" and self.sink:
            self.sink.stop()
            logger.info("Destroyed sink.")
