"""Setup definition."""

import os
import platform
from setuptools import setup, find_packages


def main():
    """Setup entry point."""

    # to get the long description
    with open('README.md') as f:
        long_description = f.read()

    # parse the requirements files
    with open('dependencies.txt') as f:
        dependency_requirements = f.read().split("\n")
    with open('requirements.txt') as f:
        install_requirements = f.read().split("\n")
    with open('requirements_dev.txt') as f:
        test_requirements = f.read().split("\n")

    # Windows doesn't need setproctitle as it will be built into an EXE anyway
    if platform.system() == 'Windows':
        install_requirements = [x for x in install_requirements \
                                if not x.startswith('setproctitle')]

    # do GObject install
    os.system(
        "cd packages/; "
        "tar xf pygobject-3.22.0.tar.xz; "
        "cd pygobject-3.22.0; "
        "sed -i '13273s/${prefix}/\/home\/ishkanan\/.pyenv\/versions\/pytooth/' configure; "
        "sed -i '13275s/${exec_prefix}/\/home\/ishkanan\/.pyenv\/versions\/pytooth/' configure; "
        "./configure; "
        "make; "
        "sudo make install; "
        "cd ..; "
        "sudo rm -Rf pygobject-3.22.0/")

    setup(
        name="pytooth",
        version="1.0.0",
        description="Linux-only wrapper library of the Bluez5 stack.",
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
            "distutils.commands": [
                "foo = mypackage.some_module:foo",
            ],
        },
        zip_safe=False
    )

if __name__ == '__main__':
    main()
