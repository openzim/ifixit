# -*- coding: utf-8 -*-

import pathlib

from setuptools import setup

root_dir = pathlib.Path(__file__).parent


def read(*names, **kwargs):
    with open(root_dir.joinpath(*names), "r") as fh:
        return fh.read()


setup(
    name="ifixit2zim",
    version=read("ifixit2zim", "VERSION").strip(),
    description="Make ZIM file from iFixit articles",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="Kiwix Team",
    author_email="dev@kiwix.org",
    url="https://kiwix.org/",
    keywords="kiwix zim offline ifixit",
    license="GPLv3+",
    packages=["ifixit2zim"],
    install_requires=[
        line.strip()
        for line in read("requirements.pip").splitlines()
        if not line.strip().startswith("#") and not line.startswith("https://")
    ],
    zip_safe=False,
    include_package_data=True,
    package_data={"": ["VERSION", "templates/*", "assets/*"]},
    entry_points={
        "console_scripts": [
            "ifixit2zim=ifixit2zim.__main__:main",
        ]
    },
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    ],
    python_requires=">=3.8",
)
