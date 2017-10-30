"""Setup entry point."""

import os
import platform

from setuptools import setup, find_packages


# to get the long description
with open('README.md') as f:
    long_description = f.read()

# parse the reqs/deps files
with open('requirements.txt') as f:
    install_requirements = f.read().split("\n")
with open('requirements_dev.txt') as f:
    test_requirements = f.read().split("\n")
with open('dependencies.txt') as f:
    dependency_requirements = f.read().split("\n")

# prepare
packages_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "packages")
src_dir = os.path.join(
    packages_dir,
    "src")
print("packages_dir = {}\nsrc_dir = {}".format(
    packages_dir, src_dir))

# compile and install sources
# NOTE: cannot use setup.py for these since cannot pass -prefix and -exec-prefix
sources = [
    ("pygobject", "3.22.0"),
    ("dbus-python", "1.2.4"),
    ("sbc", "1.2.0")
]
for lib in sources:
    print("Installing {}-{} library from source ...".format(
        lib[0], lib[1]))
    os.system(
        "cd '{srcdir}'; "
        "tar xf {libname}-{libver}.tar.gz; "
        "cd {libname}-{libver}; "
        "./configure -prefix=$VIRTUAL_ENV -exec-prefix=$VIRTUAL_ENV >/dev/null; "
        "make >/dev/null; "
        "sudo make install >/dev/null; "
        "if [ -f setup.py ]; then python setup.py install; fi; ".format(
            srcdir=src_dir,
            libname=lib[0],
            libver=lib[1]))

# go-go
setup(
    name="pytooth",
    version="1.0.0",
    description="A Linux Bluez5-based implementation of A2DP and HFP.",
    long_description=long_description,
    author="Anthony Ishkan",
    author_email="anthony.ishkan@gmail.com",
    url="https://bitbucket.org/ishkanan/pytooth",
    packages=find_packages(".", include=["*"]),
    package_dir={"": "."},
    package_data={
        "": ["*.txt", "*.rst", "*.md"]
    },
    tests_require=test_requirements,
    install_requires=install_requirements,
    dependency_links=dependency_requirements,
    entry_points={
        "console_scripts": [
            "pytooth-test = pytooth.tests.main:main",
        ],
    },
    zip_safe=False
)

# clean up working folders
print("Cleaning up source folders ...")
for lib in sources:
    os.system(
        "sudo rm -Rf '{srcdir}/{libname}-{libver}/'; ".format(
            srcdir=src_dir,
            libname=lib[0],
            libver=lib[1]))
