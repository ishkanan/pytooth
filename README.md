# Pytooth Library #

An easy-to-use wrapper library, built on [Tornado](http://www.tornadoweb.org/), for interacting with Bluez5 over the DBus API. Currently only the **A2DP** (music streaming) profile is supported. **HFP** (hands-free) is still in development.

Bluez5 documentation available in the Bluez5 [source code repository](https://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc).

# Installation #

This section details how to install Pytooth for use in a project or for development purposes.

## Virtual Environment ##

It is recommended practice to run Python applications in Python [Virtual Environments](https://virtualenv.pypa.io/en/stable/). The justifications for doing so are aplenty on the internet, so won't be repeated here. Due to pre-requisite installation requirements (for **gobject**, **dbus-python** and **sbc**) the **setup.py** installation process assumes it is contained in a Virtual Environment. If this is not possible, then the assignment to ***python_dir*** will need to be changed to point to a system-level installation of Python.

## Installation ##

For integration into a bigger project, add the appropriate steps into the project's deployment processes. The library installer is built using the [setuptools](https://setuptools.readthedocs.io/) library so it is compatible with most **setuptools**-related processes.

**Note:** this project is not listed on [PyPi](https://pypi.python.org/) at this time, so **pip** will not be able to find an installation candidate.

## Development ##

To install the library for development purposes, clone the repository and make any required changes to **setup.py** if not using a Virtual Environment. Then navigate to the folder containing **setup.py** and execute:

```
#!bash
$ python setup.py develop
```

# Contact "Us" #

The lead (read: only) developer, Anthony Ishkan (anthony.ishkan@gmail.com)