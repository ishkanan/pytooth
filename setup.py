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

# supported platform?
# dist = platform.linux_distribution()
# if "xenial" in dist:
#     dist = "xenial"
# else:
#     print("ERROR: Linux distribution is not supported.")
#     raise NotImplementedError()
dist = "xenial"

# prepare
packages_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "packages")
bin_dir = os.path.join(
    packages_dir,
    "bin/{}".format(dist))
src_dir = os.path.join(
    packages_dir,
    "src")
print("packages_dir = {}\nbin_dir = {}\nsrc_dir = {}".format(
    packages_dir, bin_dir, src_dir))

# install source libraries
# NOTE: cannot use setup.py for these since cannot pass -prefix and -exec-prefix
for lib in [("pygobject", "3.22.0", "xz"), ("dbus-python", "1.2.4", "gz")]:
    print("Installing {}-{} library from source ...".format(
        lib[0], lib[1]))
    os.system(
        "cd '{srcdir}'; "
        "tar xf {libname}-{libver}.tar.{ext}; "
        "cd {libname}-{libver}; "
        "./configure -prefix=$VIRTUAL_ENV -exec-prefix=$VIRTUAL_ENV >/dev/null; "
        "make >/dev/null; "
        "sudo make install >/dev/null; "
        "python setup.py install; ".format(
            srcdir=src_dir,
            libname=lib[0],
            libver=lib[1],
            ext=lib[2]))

# install pre-compiled libraries
os.system(
    "sudo mkdir -p /usr/local/lib; "
    "sudo chmod 755 /usr/local/lib")
for lib in [("libsbc", "1.2.0")]:
    print("Installing {}-{} pre-compiled library to /usr/local/lib ...".format(
        lib[0], lib[1]))
    os.system(
        "sudo cp '{bindir}/{libname}.so.{libver}' /usr/local/lib/; "
        "(cd /usr/local/lib && {{ sudo ln -s -f {libname}.so.{libver} {libname}.so.1 || {{ sudo rm -f {libname}.so.1 && sudo ln -s {libname}.so.{libver} {libname}.so.1; }}; }}); "
        "(cd /usr/local/lib && {{ sudo ln -s -f {libname}.so.{libver} {libname}.so || {{ sudo rm -f {libname}.so && sudo ln -s {libname}.so.{libver} {libname}.so; }}; }}); "
        "sudo ldconfig -n /usr/local/lib".format(
            bindir=bin_dir,
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
os.system(
    "sudo rm -Rf '{srcdir}/dbus-python-1.2.4/'; "
    "sudo rm -Rf '{srcdir}/pygobject-3.22.0/'; ".format(
        srcdir=src_dir))

