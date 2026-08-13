"""Apply Debian Python bootstrap compatibility before running PyInstaller."""

from PyInstaller import compat
from PyInstaller.__main__ import run


# Debian's supported Python 3.9 urllib.parse imports ipaddress, while
# PyInstaller 5.13 only adds it to base_library.zip for Python >= 3.11.4.
compat.PY3_BASE_MODULES.add("ipaddress")

run()
