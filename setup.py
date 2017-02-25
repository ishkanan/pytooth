"""Setup entry point."""

import os
import site

from setuptools import setup, find_packages


# to get the long description
with open('README.md') as f:
    long_description = f.read()

# parse the requirements files
with open('requirements.txt') as f:
    install_requirements = f.read().split("\n")
with open('requirements_dev.txt') as f:
    test_requirements = f.read().split("\n")

# pre-reqs
packages_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "packages/")
python_dir = os.path.join(site.USER_SITE, "../").replace("/", "\\/")

# parse dependency locations
with open('dependencies.txt') as f:
    dependency_requirements = f.read().replace(
        "{{ PACKAGES_DIR }}", packages_dir).split("\n")

# do GObject install
os.system(
    "cd "+packages_dir+"; "
    "tar xf pygobject-3.22.0.tar.xz; "
    "cd pygobject-3.22.0; "
    "sed -i '13273s/${prefix}/"+python_dir+"/' configure; "
    "sed -i '13275s/${exec_prefix}/"+python_dir+"/' configure; "
    "./configure; "
    "make; "
    "sudo make install; "
    "python setup.py install; ")

# do dbus-python install
os.system(
    "cd "+packages_dir+"; "
    "tar xf dbus-python-1.2.4.tar.gz; "
    "cd dbus-python-1.2.4; "
    "sed -i '12352s/${prefix}/"+python_dir+"/' configure; "
    "sed -i '12354s/${exec_prefix}/"+python_dir+"/' configure; "
    "./configure; "
    "make; "
    "sudo make install; "
    "python setup.py install; ")

# do SBC decoder install
os.system(
    "cd "+packages_dir+"; "
    "tar xf sbc-1.2.tar.gz; "
    "cd sbc-1.2; "
    "./configure; "
    "make; "
    "sudo make install; ")

setup(
    name="pytooth",
    version="1.0.0",
    description="Linux-only Bluez5-based implementation of A2DP and HFP.",
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
os.system(
    "cd "+packages_dir+"; "
    "sudo rm -Rf pygobject-3.22.0/; "
    "sudo rm -Rf sbc-1.2/; "
    "sudo rm -Rf dbus-python-1.2.4/; ")
