# Overview
An easy-to-use Bluetooth Python 3 library, built on the asynchronous [Tornado](http://www.tornadoweb.org/) framework, for interacting with Bluez5 over the DBus API. It currently supports the **A2DP** (music streaming), **HFP** (hands-free phone) and **PBAP** (phonebook transfer) profiles.

Bluez5 documentation available in the Bluez5 [source code repository](https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc).

# Operating System
Theoretically this library can run on any Linux distribution that can support the dependencies in the section below. This does mean that Windows is not supported due to the close integration with Bluez5.

# Dependencies
This library depends on many system packages and Python modules. The sections below describe each set of dependencies in detail.

## Packages: System
The table below lists the packages for an Ubuntu 18.04 (Bionic) system. The names will most likely differ for non-Ubuntu distributions. Documentation contributions are welcome!

**Package** | **Description**
--- | ---
bluez | Bluetooth stack for Linux. Minimum version 5.47 to include critical bug fixes.
dbus-x11 | X-11 dependencies for DBus
libasound2-dev | Dependency for **pyalsaaudio**
libsndfile1-dev | Dependency for **libsbc**
python-gobject | Dependency for **pydbus**
python3-pyaudio | Dependency for **pyaudio**

## Packages: Python
**Package** | **Description**
--- | ---
gobject, pygobject | Interfaces to the GTK framework
pydbus | DBus interface library
pyalsaaudio | Interface to ALSA
setproctitle | Easy identification of app in process listings
tornado | Asynchronous web/networking framework
wheel | Required for project build

## Other
Pytooth interfaces with a C-based SBC codec library called [libsbc](https://www.kernel.org/pub/linux/bluetooth/sbc-1.2.tar.xz) directly via Python **ctypes**. This allows for fast and reliable decoder code when using A2DP. The source code comes bundled with Pytooth and is built during installation.

# Installation
This section details how to configure the various depedency systems and install the Pytooth library. There are a few installation use cases:

* Integration into a larger project
* Non-interactive (via the provided test ***apps***)
* Development of the library

These instructions are generally distribution-agnostic, however configuration file locations may vary between distributions. The instructions are correct for Ubuntu and (most likely) Debian-based distros. The instructions assume a distro running **systemd**. For those that do not, the reader will need to substitute in the correct steps. Again, documentation contributions are welcome =)

## Bluetooth
Enable Bluez5 custom commands by appending **--compat** to the ```ExecStart``` section of the systemd unit file ```/lib/systemd/system/bluetooth.service```, like so:

```
ExecStart=/usr/lib/bluetooth/bluetoothd --compat
```

Restart Bluetooth with ```systemctl restart bluetooth.service```.

## DBus
Allow Pytooth to send DBus messages and claim ownership of the **ishkanan.pytooth** namespace by changing:

`<deny own="*"/>` to `<allow own="*"/>`

and

`<deny send_type="method_call"/>` to `<allow send_type="method_call"/>`

in the DBus system config file ```/usr/share/dbus-1/system.conf```. DBus should apply the changes immediately.

## Group Membership
Decide which user will be running the application/test apps and add that user to the following groups:

* audio
* lp

Existing user sessions will need to be restarted for the membership changes to take effect.

## Virtual Environment (Python 3)
It is recommended practice to run Python applications in Python [Virtual Environments](https://virtualenv.pypa.io/en/stable). The pros and cons for doing so are aplenty on the internet, and are beyond the scope of this documentation. The installer assumes it is running in a virtual environment. System-level installation of the library is currently untested.

## Pytooth Library
The final step is to install the library itself. This will differ based on the installation use case. The installer is based on Python [setuptools](https://setuptools.readthedocs.io/) however it is not currently listed on [PyPI](https://pypi.python.org/) so cannot be installed with **pip**. The file `setup.py` in the root folder is the installer entry point. The installer builds and installs all source gzips located in the **packages/src** folder (**libsbc**). Some of the commands require root privileges so the installer will prompt for elevation.

### Install: Integration into larger project
For integration into a larger project, ensure that the project's deployment processes invoke the `setup.py` script with the **install** command, for example:

```bash
$ python setup.py install
```

### Install: Non-interactive
Pytooth provides a bare-bones test script for each supported Bluetooth profile, located in the **pytooth/tests** folder. The A2DP script provides full playback functionality. The HFP script provides audio functionality but no remote control functions (e.g. answer, hang-up, etc). The PBAP script downloads the internal phonebook for example purposes, so it's not really suitable for this use case.

First, install the library with:

```bash
$ python setup.py install
```

The installer creates a test command, **pytooth-test**, that is used to launch one or more test scripts simultaneously. It is executed like so:

```bash
$ pytooth-test -c <config file>
```

where `<config file>` is a copy of (or the actual file) **pytooth/tests/test_config.json**.

**Key** | **Value**
--- | ---
preferredaddress | May contain the MAC address of a specific Bluetooth adapter (if more than one is available), or blank to use the first available one (non-deterministic)
profiles | A list of profiles to launch, where valid items are "a2dp", "hfp" and "pbap"
retryinterval | Time, in seconds, that the library will search for a suitable Bluetooth adapter to use; can usually be left at the default value (15)

### Install: Library development
To install the library for development purposes, clone the repository and invoke the `setup.py` script with the **develop** command, like so:

```bash
$ python setup.py develop
```

The test scripts can be run as described in the section above.

# Contact "Us"
The lead developer, Anthony Ishkan (anthony.ishkan@gmail.com). He only bites if he's hungover or hungry =)
