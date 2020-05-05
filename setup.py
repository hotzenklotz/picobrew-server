import sys
import os
from setuptools import setup, find_packages
from setuptools.command.install import install


VERSION = "1.0.0"


def readme():
    """print long description"""
    with open("README.md") as f:
        return f.read()


class VerifyVersionCommand(install):
    """Custom command to verify that the git tag matches our version"""

    description = "verify that the git tag matches our version"

    def run(self):
        tag = os.getenv("CIRCLE_TAG") or os.getenv("GITHUB_REF")

        if tag != VERSION:
            info = "Git tag: {0} does not match the version of this app: {1}".format(
                tag, VERSION
            )
            sys.exit(info)


setup(
    name="picobrew_server",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=["flask",],
    version=VERSION,
    description="A reverse-engineered server for the Picobrew homebrewing machines",
    long_description=readme(),
    long_description_content_type="text/markdown",
    author="Tom Herold",
    author_email="heroldtom@gmail.com",
    url="https://github.com/hotzenklotz/picobrew-server",
    download_url="https://github.com/hotzenklotz/picobrew-server/tarball/{}".format(
        VERSION
    ),
    cmdclass={"verify": VerifyVersionCommand},
    platforms="any",
    keywords=["picobrew", "zymatic", "beerxml", "beer", "brewing"],
    classifiers=["Programming Language :: Python",],
    license="MIT",
)
