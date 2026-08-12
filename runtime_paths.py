"""Shared executable and application-directory resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen_application(module_globals=None):
    """Return whether the caller runs from a frozen/compiled executable."""
    compiled = (
        module_globals is not None and "__compiled__" in module_globals
    )
    return bool(getattr(sys, "frozen", False) or compiled)


def resolve_application_directory(
    source_file, frozen=None, environment=None, executable=None
):
    """Locate assets beside a script, executable, AppImage, or macOS app."""
    environment = os.environ if environment is None else environment
    appimage = environment.get("APPIMAGE")
    if appimage:
        appimage_path = Path(appimage).resolve()
        if appimage_path.is_file():
            return appimage_path.parent

    if frozen is None:
        frozen = is_frozen_application()
    executable = sys.executable if executable is None else executable
    launch_file = executable if frozen else source_file
    directory = Path(launch_file).resolve().parent
    for parent in (directory, *directory.parents):
        if parent.suffix.lower() == ".app":
            return parent.parent
    return directory
