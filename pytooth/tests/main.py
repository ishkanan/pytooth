"""Defines a test entry point."""

import argparse
from functools import partial
import logging
import logging.config
import signal
import sys

from tornado.ioloop import PeriodicCallback

from pytooth.gi.loops import GtkMainLoop
import pytooth.tests.config
from pytooth.tests.errors import ConfigurationError


_closing = False


def signal_handler(signum, frame):
    global _closing
    _closing = True


def try_exit(gtkloop, apps):
    global _closing

    if _closing:
        for app in apps:
            try:
                app.stop()
            except Exception:
                logging.exception("Error gracefully stopping application '{}'.".format(
                    app))
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

    # make loop before connecting to DBus
    gtkloop = GtkMainLoop()

    # create common objects
    system_bus, session_bus = pytooth.init()

    # load profile test apps
    apps = []
    for profile in config["profiles"]:
        try:
            _t = __import__(
                "pytooth.tests.{}".format(profile),
                globals(),
                locals(),
                ["TestApplication"],
                0)
            apps.append(_t.TestApplication(
                session_bus=session_bus,
                system_bus=system_bus,
                config=config))
        except Exception:
            logging.exception("Possible import error of '{}' profile.".format(
                profile))
    if len(apps) == 0:
        logging.error("No valid profiles loaded - exiting.")
        return

    # run the test apps
    logging.info("Running...")
    signal.signal(signal.SIGINT, signal_handler)
    PeriodicCallback(partial(
        try_exit,
        gtkloop=gtkloop,
        apps=apps), 500).start()
    for app in apps:
        app.start()
    gtkloop.start()
