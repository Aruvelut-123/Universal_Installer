"""Linux Qt display-backend selection shared by both application binaries."""

import os
import platform


def configure_linux_qt_platform(environment=None, system_name=None):
    """Prefer native Wayland with X11 fallback without overriding user choice."""
    environment = os.environ if environment is None else environment
    system_name = platform.system() if system_name is None else system_name
    if system_name.lower() != "linux" or environment.get("QT_QPA_PLATFORM"):
        return environment.get("QT_QPA_PLATFORM")

    session_type = environment.get("XDG_SESSION_TYPE", "").lower()
    has_wayland = bool(environment.get("WAYLAND_DISPLAY"))
    has_x11 = bool(environment.get("DISPLAY"))
    if has_wayland or session_type == "wayland":
        # Qt tries entries from left to right. This stays native on Wayland and
        # falls back to XCB when a compositor or the Wayland plugin is missing.
        selected = "wayland;xcb" if has_x11 else "wayland"
    elif has_x11 or session_type == "x11":
        selected = "xcb"
    else:
        # Leave headless/offscreen/minimal selection to Qt or the caller.
        return None
    environment["QT_QPA_PLATFORM"] = selected
    return selected
