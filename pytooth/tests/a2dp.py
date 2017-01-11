"""Defines a test entry point."""

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
        self.a2dp = AdvancedAudioProfile(
            system_bus=bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.instance())
        self.a2dp.on_adapter_connected_changed = self.adapter_connected_changed
        self.a2dp.on_streaming_state_changed = self.streaming_state_changed
        self.a2dp.on_media_transport_disconnect = self.media_transport_disconnect

    def start(self):
        self.a2dp.start()

    def stop(self):
        self.a2dp.set_discoverable(enabled=False)
        self.a2dp.set_pairable(enabled=False)
        self.a2dp.stop()

    def adapter_connected_changed(self, adapter):
        if adapter.connected:
            adapter.set_discoverable(enabled=True)
            adapter.set_pairable(enabled=True)

    def streaming_state_changed(self, adapter, transport, state):
        if state == "playing" and self.sink is None:
            self.sink = PortAudioSink(
                card_name="pulse",
                transport=transport)
            self.sink.start()
            logger.info("Built new sink.")

    def media_transport_disconnect(self, adapter, transport):
        if self.sink:
            self.sink.stop()
        self.sink = None
        logger.info("Destroyed sink.")
