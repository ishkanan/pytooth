"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.hfp import HandsFreeProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.audio.decoders import SBCDecoder
from pytooth.audio.sinks import DirectFileSink, PortAudioSink

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

    def _adapter_connected_changed(self, adapter, connected):
        # be discoverable if adapter is connected
        self.hfp.set_discoverable(enabled=connected)
        self.hfp.set_pairable(enabled=connected)

    def _audio_connected(self, adapter, socket, mtu, peer):
        # we make a sink
        # self.sink = PortAudioSink(
        #     decoder=SBCDecoder(
        #         libsbc_so_file="/usr/local/lib/libsbc.so.1.2.0"),
        #     socket_or_fd=socket,
        #     read_mtu=mtu,
        #     card_name="pulse")
        #logger.info("Built new PortAudio sink.")
        self.sink = DirectFileSink(
            socket_or_fd=socket,
            filename="/home/vagrant/pytooth/raw_sco.out")
        self.sink.start()
        logger.info("Built new DirectFileSink sink.")

    def _audio_setup_error(self, adapter, error):
        pass

    def _device_connected_changed(self, device, connected, phone):
        self.phone = phone

    def _profile_status_changed(self, available):
        pass
