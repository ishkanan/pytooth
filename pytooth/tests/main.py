"""Defines a test entry point."""

import argparse
from functools import partial
import logging
import logging.config
import signal
import sys

from tornado.ioloop import IOLoop, PeriodicCallback

import pytooth
from pytooth.a2dp import AdvancedAudioProfile
from pytooth.adapters import OpenPairableAdapter
from pytooth.gi import GtkMainLoop
from pytooth.a2dp.sinks import FileSBCSink, PortAudioSink
import pytooth.tests.config
from pytooth.tests.errors import ConfigurationError


_closing = False
_sink = None

def signal_handler(signum, frame):
    global _closing
    _closing = True

def try_exit(gtkloop, a2dp):
    global _closing, _sink

    if _closing:
        if _sink:
            _sink.stop()
            logging.debug("Destroyed sink.")
        try:
            a2dp.set_discoverable(enabled=False)
            a2dp.set_pairable(enabled=False)
        except Exception:
            logging.exception("Error resetting disc/pair.")
        a2dp.stop()
        gtkloop.stop()
        logging.info("Gracefully stopped. Have a nice day.")

def adapter_connected_changed(adapter):
    if adapter.connected:
        adapter.set_discoverable(enabled=True)
        adapter.set_pairable(enabled=True)

def streaming_state_changed(adapter, transport, state):
    global _sink

    if state == "playing" and _sink is None:
        _sink = PortAudioSink(
            card_name="pulse",
            transport=transport)
        _sink.start()
        logging.debug("Built new sink.")

def media_transport_disconnect(adapter, transport):
    global _sink

    if _sink:
        _sink.stop()
    _sink = None
    logging.debug("Destroyed sink.")

def main():
    args = sys.argv

    # process (CLI) args
    parser = argparse.ArgumentParser(
        prog="pytooth-test" if len(args) == 0 else args[0],
        description="Test app for pytooth library.")
    parser.add_argument(
        "--config", "-c",
        type=str,
        required=True)
    v = vars(parser.parse_args(args[1:]))

    # process configuration file
    config = pytooth.tests.config.get_config(filename=v["config"])
    try:
        pytooth.tests.config.validate_config(config=config)
    except ConfigurationError as e:
        print("ERROR: Bad configuration found - {}".format(e))
        sys.exit(1)

    # apply logging configuration
    if "logging" in config:
        try:
            logging.config.dictConfig(config["logging"])
            logging.info("Applied logging configuration.")
        except Exception as e:
            print("WARNING! Could not parse logging configuration, logging may "
                "not be configured properly - {}".format(e))

    # init
    bus = pytooth.init()

    # A2DP
    a2dp = AdvancedAudioProfile(
        system_bus=bus,
        adapter_class=OpenPairableAdapter,
        preferred_address=config["preferredaddress"],
        retry_interval=config["retryinterval"],
        io_loop=IOLoop.instance())
    a2dp.on_adapter_connected_changed = adapter_connected_changed
    a2dp.on_streaming_state_changed = streaming_state_changed
    a2dp.on_media_transport_disconnect = media_transport_disconnect

    # run the test app
    logging.info("Running...")
    gtkloop = GtkMainLoop(io_loop=IOLoop.instance())
    signal.signal(signal.SIGINT, signal_handler)
    PeriodicCallback(partial(
        try_exit,
        gtkloop=gtkloop,
        a2dp=a2dp), 500).start()
    a2dp.start()
    gtkloop.start()
