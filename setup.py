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
bin_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "packages/bin/{}".format(dist))

# install pygobject
os.system(
    "cd '{bindir}/pygobject-3.22.0'; "
    "python setup.py install; ".format(
        bindir=bin_dir))

# install external libraries
os.system(
    "sudo mkdir -p /usr/local/lib; "
    "sudo chmod 755 /usr/local/lib")
for lib in [("libliquid", "1.2.0"), ("libsbc", "1.2.0")]:
    print("Installing {} external library to /usr/local/lib ...".format(lib))
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
    packages=find_packages(exclude=["pytooth.tests"]),
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
# os.system(
#     "cd "+packages_dir+"; "
#     "sudo rm -Rf pygobject-3.22.0/; "
#     "sudo rm -Rf sbc-1.2/; ")
