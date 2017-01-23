"""Defines a test application for A2DP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.a2dp import AdvancedAudioProfile
from pytooth.a2dp.sinks import FileSBCSink, PortAudioSink
from pytooth.adapters import OpenPairableAdapter

logger = logging.getLogger("a2dp-test")


class TestApplication:

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
        a2dp.on_device_connected_changed = self._device_connected_changed
        a2dp.on_media_setup_error = self._
        a2dp.on_media_stream_state_changed = self._media_streaming_state_changed
        a2dp.on_profile_status_changed = self._profile_status_changed
        self.a2dp = a2dp

    def start(self):
        self.a2dp.start()

    def stop(self):
        # cleanup
        self.a2dp.set_discoverable(enabled=False)
        self.a2dp.set_pairable(enabled=False)
        self.a2dp.stop()

    def _media_setup_error(self, adapter, error):
        pass

    def _media_streaming_state_changed(self, adapter, transport, state):
        # we make sinks or destroy them...
        if state == "playing" and self.sink is None:
            self.sink = PortAudioSink(
                card_name="pulse",
                transport=transport)
            self.sink.start()
            logger.info("Built new sink.")
        elif state == "released" and self.sink:
            self.sink.stop()
            self.sink = None
            logger.info("Destroyed sink.")

    def _profile_status_changed(self, available):
        # be discoverable if profile is A-OK
        adapter.set_discoverable(enabled=available)
        adapter.set_pairable(enabled=available)
