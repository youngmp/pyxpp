"""
pip install .        (or: pip install -e .)

Builds pyxpp/_libxpp.{so,dylib} from the vendored XPPAUT sources with
build_lib.py before packaging.  Needs a C compiler; no X11.
"""
import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop

ROOT = Path(__file__).resolve().parent


def _build():
    subprocess.check_call([sys.executable, str(ROOT / "build_lib.py")])


class BuildPy(build_py):
    def run(self):
        _build()
        super().run()


class Develop(develop):
    def run(self):
        _build()
        super().run()


setup(cmdclass={"build_py": BuildPy, "develop": Develop})
