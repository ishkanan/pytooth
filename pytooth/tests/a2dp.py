"""Defines a test application for A2DP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.a2dp import AdvancedAudioProfile
from pytooth.a2dp.sbc import SBCDecoder
from pytooth.a2dp.sinks import PortAudioSink
from pytooth.adapters import OpenPairableAdapter

logger = logging.getLogger(__name__)


class TestApplication:
    """Test application for the A2DP profile. The logic of this code is suitable
    for use in a real-world application.
    """

    def __init__(self, bus, config):
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
        # error setting up audio link, log and forget
        logger.error("Cannot establish audio link on adapter {} - {}".format(
            adapter, error))

    def _audio_stream_state_changed(self, adapter, transport, state):
        # we make sinks or destroy them...
        if state == "playing" and self.sink is None:
            self.sink = PortAudioSink(
                decoder=SBCDecoder(
                    libsbc_so_file="/usr/local/lib/libsbc.so.1.2.0"),
                socket=transport.socket,
                read_mtu=transport.read_mtu,
                card_name="pulse",
                buffer_secs=2)
            self.sink.start()
            logger.info("Built new PortAudioSink with SBCDecoder.")
        elif state == "released" and self.sink:
            self.sink.stop()
            self.sink = None
            logger.info("Destroyed PortAudioSink.")

    def _audio_track_changed(self, track):
        logger.info("Track changed - {}".format(track))
        
    def _device_connected_changed(self, device, connected):
        logger.info("Device {} has {}connected.".format(
            "" if connected else "not "))

    def _profile_status_changed(self, available):
        logger.info("A2DP profile is {}avaiable.".format(
            "" if avaiable else "not "))
