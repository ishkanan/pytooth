"""Defines a test entry point."""

import argparse
from functools import partial
import logging
import logging.config
import signal
import sys

from tornado.ioloop import IOLoop, PeriodicCallback

from pytooth.gi import GtkMainLoop
from pytooth.tests.a2dp import TestApplication as a2dp
import pytooth.tests.config
from pytooth.tests.errors import ConfigurationError


_closing = False

def signal_handler(signum, frame):
    global _closing
    _closing = True

def try_exit(gtkloop, app):
    global _closing

    if _closing:
        app.stop()
        gtkloop.stop()
        logging.info("Gracefully stopped. Have a nice day.")

def main():
    args = sys.argv

    # process (CLI) args
    parser = argparse.ArgumentParser(
        prog="pytooth-test" if len(args) == 0 else args[0],
        description="Test app launcher for the pytooth library.")
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

    # load profile test app
    try:
        _t = __import__(
            "pytooth.tests.{}".format(config["profile"]),
            globals(),
            locals(),
            ["TestApplication"],
            0)
    except Exception:
        logging.critical("Import error. Is your profile key valid?")
        return
    app = _t.TestApplication(config=config)

    # run the test app
    logging.info("Running...")
    gtkloop = GtkMainLoop(io_loop=IOLoop.instance())
    signal.signal(signal.SIGINT, signal_handler)
    PeriodicCallback(partial(
        try_exit,
        gtkloop=gtkloop,
        app=app), 500).start()
    app.start()
    gtkloop.start()
