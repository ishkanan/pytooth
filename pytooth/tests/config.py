"""Provides helper methods for handling configuration definition and validation.
"""

import json

from pytooth.tests.errors import ConfigurationError


def get_config(filename):
    """Reads in the specified JSON-formatted file and returns it as a dictionary
    using the ``json`` module. Throws ``dishtube.errors.ConfigurationError``
    if an error occurred.
    """

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        raise ConfigurationError(e)


def validate_config(config):
    """Validates the supplied configuration. Validation does not include checks
    for valid values parses the data against a defined configuration and
    returns a dictionary if validation succeeded.
    Throws a ``ConfigurationError`` error if validation failed.
    """

    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary.")

    # A JSON-formatted file containing logging configuration.
    arg = config.get("logging", {})
    if not isinstance(arg, dict):
        raise ConfigurationError("'logging' must be dictionary.")

    # Interval in seconds to wait between adapter checks
    arg = config.get("retryinterval", 0)
    try:
        if arg < 5:
            raise ValueError()
    except Exception:
        raise ConfigurationError("'retryinterval' must be at least 5.")

    # List of profiles
    arg = config.get("profiles", [])
    if not isinstance(arg, list):
        raise ConfigurationError("'profiles' must be a non-empty list.")
    if len(arg) == 0:
        raise ConfigurationError("'profiles' must be a non-empty list.")

    # Optional string properties
    for s in ["preferredaddress"]:
        arg = config.get(s, None)
        if not isinstance(arg, str):
            raise ConfigurationError(
                "'{}' must be a string.".format(s))
