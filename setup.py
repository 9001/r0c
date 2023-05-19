#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function

import os
import sys
from glob import glob
from shutil import rmtree

try:
    # need setuptools to build wheel
    from setuptools import setup, Command

    setuptools_available = True

except ImportError:
    # works in a pinch
    from distutils.core import setup, Command

    setuptools_available = False

if "bdist_wheel" in sys.argv and not setuptools_available:
    print("cannot build wheel without setuptools")
    sys.exit(1)


def mglob(dirname, extensions):
    ret = []
    for ext in extensions:
        ret.extend(glob(dirname + "/*." + ext))
    return ret


NAME = "r0c"
data_files = [
    ("share/doc/r0c", ["README.md", "LICENSE"]),
    ("share/doc/r0c/help", mglob("docs", ["md"])),
    ("share/doc/r0c/clients", glob("clients/*")),
]
manifest = ""
for dontcare, files in data_files:
    for fn in files:
        manifest += "include {0}\n".format(fn)

here = os.path.abspath(os.path.dirname(__file__))

with open(here + "/MANIFEST.in", "wb") as f:
    f.write(manifest.encode("utf-8"))

with open(here + "/README.md", "rb") as f:
    md = f.read().decode("utf-8")

    md = md.replace(
        "(docs/r0c.png)",
        "(https://raw.githubusercontent.com/9001/r0c/master/docs/r0c.png)",
    )

    for kw in ["docs/help-", "docs/", "clients/"]:
        md = md.replace(
            "({0}".format(kw),
            "(https://github.com/9001/r0c/blob/master/{0}".format(kw),
        )

    long_description = md


about = {}
with open(os.path.join(here, NAME, "__version__.py"), "rb") as f:
    exec(f.read().decode("utf-8"), about)

# about["__version__"] = "0.0.4"


class clean2(Command):
    description = "Cleans the source tree"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        os.system("{0} setup.py clean --all".format(sys.executable))

        try:
            rmtree("./dist")
        except:
            pass

        try:
            rmtree("./r0c.egg-info")
        except:
            pass

        nuke = []
        for (dirpath, dirnames, filenames) in os.walk("."):
            for fn in filenames:
                if (
                    fn.startswith("MANIFEST")
                    or fn.endswith(".pyc")
                    or fn.endswith(".pyo")
                    or fn.endswith(".pyd")
                ):
                    nuke.append(dirpath + "/" + fn)

        for fn in nuke:
            os.unlink(fn)


args = {
    "name": NAME,
    "version": about["__version__"],
    "description": "retr0chat telnet/vt100 chat server",
    "long_description": long_description,
    "long_description_content_type": "text/markdown",
    "author": "ed",
    "author_email": "r0c@ocv.me",
    "url": "https://github.com/9001/r0c",
    "license": "MIT",
    "data_files": data_files,
    "classifiers": [
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: IronPython",
        "Programming Language :: Python :: Implementation :: Jython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Environment :: Console",
        "Environment :: No Input/Output (Daemon)",
        "Topic :: Communications :: Chat",
        "Topic :: Terminals :: Telnet",
    ],
    "cmdclass": {"clean2": clean2},
}


if setuptools_available:
    args.update(
        {
            "install_requires": [],
            "include_package_data": True,
            "packages": ["r0c"],
            "entry_points": {"console_scripts": ["r0c = r0c.__main__:main"]},
        }
    )
else:
    args.update({"packages": ["r0c"], "scripts": ["bin/r0c"]})


# import pprint
# pprint.PrettyPrinter().pprint(args)
# sys.exit(0)

setup(**args)
