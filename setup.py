"""Setup definition."""
import platform
from setuptools import setup, find_packages

def main():
    """Main entry point."""

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

    # Windows doesn't need setproctitle because it will be built into an EXE anyway
    if platform.system() == 'Windows':
        install_requirements = [x for x in install_requirements \
                                if not x.startswith('setproctitle')]

    setup(
        name="carputer",
        version="1.0.0",
        description="Linux-based web app with features common to car headunits.",
        long_description=long_description,
        author="Anthony Ishkan",
        author_email="anthony.ishkan@gmail.com",
        url="https://bitbucket.org/ishkanan/carputer",
        packages=find_packages(exclude=["carputer.tests"]),
        package_data={
            "": ["*.txt", "*.rst", "*.md"]
        },
        tests_require=test_requirements,
        install_requires=install_requirements,
        dependency_links=dependency_requirements,
        entry_points={
            "console_scripts": [
                "carputer = carputer.main:main",
                "carputer-gcal = carputer.gcal.main:main",
            ]
        },
        zip_safe=False
    )

if __name__ == '__main__':
    main()
