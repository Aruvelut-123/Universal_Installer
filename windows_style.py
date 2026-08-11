"""Small Windows-native Qt and DWM compatibility layer."""

from __future__ import annotations

import ctypes
import os
import platform
import sys


def _version_tuple(version_info=None):
    if version_info is None:
        getter = getattr(sys, "getwindowsversion", None)
        if getter is None:
            return (0, 0, 0)
        version_info = getter()
    if isinstance(version_info, (tuple, list)):
        values = version_info
    else:
        values = (
            getattr(version_info, "major", 0),
            getattr(version_info, "minor", 0),
            getattr(version_info, "build", 0),
        )
    padded = list(values[:3]) + [0, 0, 0]
    return tuple(int(value) for value in padded[:3])


def windows_style_profile(version_info=None, system_name=None):
    """Identify the host generation while leaving its visuals to UxTheme."""
    system_name = platform.system() if system_name is None else system_name
    if system_name.lower() != "windows":
        return {"name": "standard", "version": (0, 0, 0), "mica": False}
    version = _version_tuple(version_info)
    if version >= (10, 0, 22000):
        name = "windows11"
    elif version >= (10, 0, 10240):
        name = "windows10"
    elif version >= (6, 2, 9200):
        name = "windows8"
    else:
        name = "windows7"
    return {"name": name, "version": version, "mica": name == "windows11"}


def configure_windows_qt_style(application, version_info=None, system_name=None):
    """Select Qt's UxTheme-backed style and respect an explicit user override."""
    profile = windows_style_profile(version_info, system_name)
    if (
        profile["name"] == "standard"
        or os.environ.get("QT_STYLE_OVERRIDE")
    ):
        return profile
    try:
        try:
            from PySide6.QtWidgets import QStyleFactory
        except ImportError:
            from PySide2.QtWidgets import QStyleFactory
        available = {name.casefold(): name for name in QStyleFactory.keys()}
        style_name = available.get("windowsvista") or available.get("windows")
        if style_name:
            application.setStyle(style_name)
    except (ImportError, RuntimeError):
        pass
    return profile


def windows_app_theme(default="light"):
    """Read the Windows application color preference for the native title bar."""
    if platform.system().lower() != "windows":
        return default
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
    except (ImportError, OSError):
        return default


def apply_windows_window_effects(window, theme="light", profile=None):
    """Apply guarded native DWM hints only where the host supports them."""
    profile = profile or windows_style_profile()
    if profile["name"] == "standard" or platform.system().lower() != "windows":
        return False
    try:
        hwnd = ctypes.c_void_p(int(window.winId()))
        setter = ctypes.windll.dwmapi.DwmSetWindowAttribute

        def set_attribute(attribute, value):
            data = ctypes.c_int(value)
            return setter(
                hwnd,
                ctypes.c_uint(attribute),
                ctypes.byref(data),
                ctypes.sizeof(data),
            ) == 0

        applied = False
        if profile["version"] >= (10, 0, 17763):
            dark = 1 if theme == "dark" else 0
            applied = set_attribute(20, dark) or set_attribute(19, dark)
        if profile["name"] == "windows11":
            applied = set_attribute(33, 2) or applied  # rounded corners
            applied = set_attribute(38, 2) or applied  # Mica main-window backdrop
        return applied
    except (AttributeError, OSError, TypeError, ValueError):
        return False
