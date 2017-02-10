# Pytooth Library

An easy-to-use wrapper library, built on [Tornado](http://www.tornadoweb.org/), for interacting with Bluez5 over the DBus API. Currently only the **_A2DP_** (music streaming) profile is supported. **_HFP_** (hands-free) is still in development.

Bluez5 documentation available in the Bluez5 [source code repository](https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc).

# Dependencies

The Pytooth library requirements are listed in **_requirements.txt_**. Three (3) of those libraries are included in the Pytooth repository (in the **_packages_** folder) and are automatically built/installed during the installation process.

## System packages

There are a number of system packages that are required by the Python library dependencies. The table lists the packages for a Fedora system; the names are different for other distributions.

#### GTK 4 (for DBus)
* gobject-introspection
* gobject-introspection-devel
* python3-cairo-devel
* cairo-gobject-devel

#### SBC (default A2DP codec)
* libsndfile-devel

#### Bluetooth / DBus / Audio
* bluez
* dbus-glib-devel
* dbus-x11
* pulseaudio
* alsa-plugins-pulseaudio
* portaudio
* portaudio-devel
* python3-pyaudio

## Python packages

   |   
--- | ---
coverage | Coverage reporter for Nose, when automated tests eventually get written
dbus-python | DBus library. Could not use **_pydbus_** due to issues with Unix sockets
nose | Test framework/runner
pyaudio | Interface to the PortAudio application
pygobject | Interface to the GTK framework
setproctitle | Easy identification of app in process listings
tornado | Asynchronous web/networking framework

# Installation

This section details how to install Pytooth for use in a project or for development purposes.

## Virtual Environment ##

It is recommended practice to run Python applications in Python [Virtual Environments](https://virtualenv.pypa.io/en/stable/). The justifications for doing so are aplenty on the internet, so won't be repeated here. Due to pre-requisite installation requirements (for **gobject**, **dbus-python** and **sbc**) the **setup.py** installation process assumes it is contained in a Virtual Environment. If this is not possible, then the assignment to ***python_dir*** will need to be changed to point to a system-level installation of Python.

## Project Integration

For integration into a bigger project, add the appropriate steps into the project's deployment processes. The library installer is built using the [setuptools](https://setuptools.readthedocs.io/) library so it is compatible with most **setuptools**-related processes.

**Note:** this project is not listed on [PyPi](https://pypi.python.org/) at this time, so **pip** will not be able to find an installation candidate.

## Development

To install the library for development purposes, clone the repository and make any required changes to **setup.py** if not using a Virtual Environment. Then navigate to the folder containing **setup.py** and execute:

```
#!bash
$ python setup.py develop
```

# Contact "Us"

The lead (read: only) developer, Anthony Ishkan (anthony.ishkan@gmail.com)