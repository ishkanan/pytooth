"""Defines a test application for A2DP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.a2dp import AdvancedAudioProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.audio.decoders.sbc import SBCDecoder
from pytooth.audio.sinks import DirectFileSink, PortAudioSink

logger = logging.getLogger("a2dp-test")


class TestApplication:
    """Test application for the A2DP profile.
    """

    def __init__(self, config):
        # init
        bus = pytooth.init()

        self.sink = None

        # profile
        a2dp = AdvancedAudioProfile(
            system_bus=bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.instance())
        a2dp.on_adapter_connected_changed = self._adapter_connected_changed
        a2dp.on_audio_setup_error = self._audio_setup_error
        a2dp.on_audio_stream_state_changed = self._audio_stream_state_changed
        a2dp.on_audio_track_changed = self._audio_track_changed
        a2dp.on_device_connected_changed = self._device_connected_changed
        a2dp.on_profile_status_changed = self._profile_status_changed
        self.a2dp = a2dp

    def start(self):
        # let's go
        self.a2dp.start()

    def stop(self):
        # cleanup
        self.a2dp.set_discoverable(enabled=False)
        self.a2dp.set_pairable(enabled=False)
        self.a2dp.stop()
        if self.sink:
            self.sink.stop()
            self.sink = None

    def _adapter_connected_changed(self, adapter, connected):
        # be discoverable if adapter is connected
        self.a2dp.set_discoverable(enabled=connected)
        self.a2dp.set_pairable(enabled=connected)

    def _audio_setup_error(self, adapter, error):
        pass

    def _audio_stream_state_changed(self, adapter, transport, state):
        # we make sinks or destroy them...
        if state == "playing" and self.sink is None:
            self.sink = PortAudioSink(
                decoder=SBCDecoder(
                    libsbc_so_file="/usr/local/lib/libsbc.so.1.2.0"),
                socket_or_fd=transport.fd,
                read_mtu=transport.read_mtu,
                card_name="pulse")
            # self.sink = DirectFileSink(
            #     socket_or_fd=transport.fd,
            #     filename="/home/vagrant/pytooth/raw_a2dp.out")
            self.sink.start()
            logger.info("Built new sink.")
        elif state == "released" and self.sink:
            self.sink.stop()
            self.sink = None
            logger.info("Destroyed sink.")

    def _audio_track_changed(self, track):
        # track changed
        logger.info("Track changed - {}".format(track))
        
    def _device_connected_changed(self, device, connected):
        pass

    def _profile_status_changed(self, available):
        pass
