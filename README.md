# Overview
An easy-to-use Bluetooth Python 3 library, built on the asynchronous [Tornado](http://www.tornadoweb.org/) framework, for interacting with Bluez5 over the DBus API. It currently supports the **A2DP** (music streaming), **HFP** (hands-free phone) and **PBAP** (phonebook transfer) profiles.

Bluez5 documentation available in the Bluez5 [source code repository](https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc).

# Operating System
Theoretically this library can run on any Linux distribution that can support the dependencies in the section below. This does mean that Windows is not supported due to the close integration with Bluez5.

# Dependencies
This library depends on many system packages and Python modules. The sections below describe each set of dependencies in detail.

## Packages: System
The table below lists the packages for an Ubuntu 16.04 (Xenial) system. The names will most likely differ for non-Ubuntu distributions. Documentation contributions are welcome!

**Package** | **Description**
--- | ---
bluez | Bluetooth stack for Linux. Must use version 5.43 or above due to fatal bug in earlier versions
dbus-x11 | X-11 dependencies for DBus
gobject-introspection | Dependency for **pygobject**
libasound2-plugins | Allows ALSA to play/capture audio via PulseAudio
libcairo2-dev | Dependency for **pygobject**
libdbus-1-dev | Dependency for **dbus-python**
libdbus-glib-1-dev | Dependency for **dbus-python**
libffi-dev | Dependency for **pygobject**
libgirepository1.0-dev | Dependency for **pygobject**
libsndfile1-dev | Dependency for **libsbc**
portaudio19-dev | Dependency for **pyaudio**
pulseaudio | Advanced sound server for Linux
python3-cairo-dev | Dependency for **pygobject**
python3-cairo-dev | Dependency for **pygobject**
python3-dev | Dependency for **pygobject** and **dbus-python**
python3-gi | Dependency for **pygobject**
python3-pyaudio | Dependency for **pyaudio**

## Packages: Python
**Package** | **Description**
--- | ---
coverage | Coverage reporter for Nose, when automated tests eventually get written
dbus-python | DBus library. Could not use [pydbus](https://github.com/LEW21/pydbus) due to issues with Unix socket interpretation/translation
nose | Test framework/runner
pyaudio | Interface to the [PortAudio](http://www.portaudio.com) application
pygobject | Interface to the GTK framework
setproctitle | Easy identification of app in process listings
tornado | Asynchronous web/networking framework

## Other
Pytooth interfaces with a C-based SBC codec library called [libsbc](https://www.kernel.org/pub/linux/bluetooth/sbc-1.2.tar.xz) directly via Python **ctypes**. This allows for fast and reliable decoder code when using A2DP. The source code comes bundled with Pytooth and is built during installation.

# Installation
This section details how to configure the various depedency systems and install the Pytooth library. There are a few installation use cases:

* Integration into a larger project
* Non-interactive (via the provided test ***apps***)
* Development of the library

These instructions are generally distribution-agnostic, however configuration file locations may vary between distributions. The instructions are correct for Ubuntu and (most likely) Debian-based distros. The instructions assume a distro running **systemd**. For those that do not, the reader will need to substitute in the correct steps. Again, documentation contributions are welcome =)

## Bluetooth
Enable Bluez5 custom commands by appending **--compat** to the ```ExecStart``` section of the systemd unit file ```/usr/lib/systemd/system/bluetooth.service```, like so:

```
ExecStart=/usr/libexec/bluetooth/bluetoothd --compat
```

Restart Bluetooth with ```systemctl restart bluetooth.service```.

## DBus
Allow Pytooth to send DBus messages and claim ownership of the **ishkanan.pytooth** namespace by changing:

```
<deny own="*"/>
```
to
```
<allow own="*"/>
```

and

```
<deny send_type="method_call"/>
```
to
```
<allow send_type="method_call"/>
```

in the DBus system config file ```/usr/share/dbus-1/system.conf```. DBus should apply the changes immediately.

## PulseAudio
PulseAudio enables its Bluetooth plugin by default. This interferes with Pytooth operation and must be disabled. Edit the file ```/etc/pulse/default.pa``` and comment out the following lines:

```
### Automatically load driver modules for Bluetooth hardware
.ifexists module-bluetooth-policy.so
load-module module-bluetooth-policy
.endif

.ifexists module-bluetooth-discover.so
load-module module-bluetooth-discover
.endif
```

## Group Membership
Decide which user will be running the application/test apps and add that user to the following groups:

* audio
* lp

If the user has active terminal sessions, then they will need to log out and back in for the membership changes to take effect.

## Virtual Environment (Python 3)
It is recommended practice to run Python applications in Python [Virtual Environments](https://virtualenv.pypa.io/en/stable). The pros and cons for doing so are aplenty on the internet, so won't be repeated here. The installer assumes it is running in a virtual environment. Note that system-level installation of the library is currently untested.

## Pytooth Library
The final step is to install the library itself. This will differ based on the installation use case. The installer is based on Python [setuptools](https://setuptools.readthedocs.io/) however it is not currently listed on [PyPI](https://pypi.python.org/) so cannot be installed with **pip**. The file ```setup.py``` in the root folder is the installer entry point. The installer builds and installs all source gzips located in the **packages/src** folder (**dbus-python**, **pygobject** and **libsbc**). Some of the commands require root privileges so the installer will prompt for elevation if not run as root (e.g. with **sudo**).

### Install: Integration into larger project
For integration into a larger project, ensure that the project's deployment processes invoke the ```setup.py``` script with the **install** command, for example:

```
#!bash
$ python setup.py install
```

### Install: Non-interactive
Pytooth provides a bare-bones test script for each supported Bluetooth profile (A2DP and HFP), located in the **pytooth/tests** folder. The A2DP script provides full playback functionality, where the HFP script provides audio functionality but no remote control functions (e.g. answer, hang-up, etc).

First, install the library with:

```
#!bash
$ python setup.py install
```

The installer creates a test command, **pytooth-test**, that is used to launch one or more test scripts simultaneously. It is executed like so:

```
#!bash
$ pytooth-test -c <config file>
```

where ```<config file>``` is a copy of (or the actual file) **pytooth/tests/test_config.json**.

**Key** | **Value**
--- | ---
preferredaddress | May contain the MAC address of a specific Bluetooth adapter (if more than one is available), or blank to use the first available one (non-deterministic)
profiles | A list of profiles to launch, where valid items are "a2dp" and "hfp"
retryinterval | Time, in seconds, that the library will search for a suitable Bluetooth adapter to use; can usually be left at the default value (15)

### Install: Library development
To install the library for development purposes, clone the repository and invoke the ```setup.py``` script with the **develop** command, like so:

```
#!bash
$ python setup.py develop
```

The test scripts can be run as described in the section above.

# Contact "Us"
The lead developer, Anthony Ishkan (anthony.ishkan@gmail.com). He only bites if he's hungover or hungry =)
