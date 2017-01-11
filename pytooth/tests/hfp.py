"""Defines a test application for HFP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.hfp import HandsFreeProfile
from pytooth.adapters import OpenPairableAdapter

logger = logging.getLogger("hfp-test")


class TestApplication:

    def __init__(self, config):
        # init
        bus = pytooth.init()

        # profile
        self.hfp = HandsFreeProfile(
            system_bus=bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.instance())
        self.hfp.on_adapter_connected_changed = self.adapter_connected_changed

    def start(self):
        self.hfp.start()

    def stop(self):
        self.hfp.set_discoverable(enabled=False)
        self.hfp.set_pairable(enabled=False)
        self.hfp.stop()

    def adapter_connected_changed(self, adapter):
        if adapter.connected:
            adapter.set_discoverable(enabled=True)
            adapter.set_pairable(enabled=True)
