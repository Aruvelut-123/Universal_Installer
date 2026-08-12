"""Linux Qt display-backend selection shared by both application binaries."""

import os
import platform


def configure_linux_qt_platform(environment=None, system_name=None):
    """Use Qt's X11 backend on Linux and disable native Wayland sessions."""
    environment = os.environ if environment is None else environment
    system_name = platform.system() if system_name is None else system_name
    if system_name.lower() != "linux":
        return environment.get("QT_QPA_PLATFORM")

    explicit_platform = environment.get("QT_QPA_PLATFORM")
    if explicit_platform and "wayland" not in explicit_platform.lower():
        return explicit_platform

    session_type = environment.get("XDG_SESSION_TYPE", "").lower()
    has_x11 = bool(environment.get("DISPLAY"))
    has_wayland_session = bool(
        environment.get("WAYLAND_DISPLAY") or session_type == "wayland"
    )
    if not (has_x11 or session_type == "x11" or has_wayland_session):
        # Leave headless/offscreen/minimal selection to Qt or the caller.
        return None
    environment["QT_QPA_PLATFORM"] = "xcb"
    return "xcb"
