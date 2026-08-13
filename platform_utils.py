"""Shared runtime, responsive Qt, and Windows integration helpers."""

from __future__ import annotations

import ctypes
import os
import platform
import sys
from pathlib import Path


def is_frozen_application(module_globals=None):
    """Return whether the caller runs from a frozen/compiled executable."""
    return bool(getattr(sys, "frozen", False))


def resolve_application_directory(
    source_file, frozen=None, environment=None, executable=None
):
    """Locate assets beside a script, executable, or macOS app."""
    if frozen is None:
        frozen = is_frozen_application()
    executable = sys.executable if executable is None else executable
    launch_file = executable if frozen else source_file
    directory = Path(launch_file).resolve().parent
    for parent in (directory, *directory.parents):
        if parent.suffix.lower() == ".app":
            return parent.parent
    return directory


def responsive_ui_metrics(width, height):
    """Return bounded wizard dimensions derived from the current window size."""
    width = max(1, int(width))
    height = max(1, int(height))
    compact = width < 720 or height < 520
    return {
        "horizontal_margin": max(14, min(32, width // 32)),
        "vertical_margin": max(12, min(24, height // 32)),
        "spacing": 8 if compact else 12,
        "header_height": max(48, min(108, round(height * 0.14))),
        "sidebar_width": max(128, min(280, round(width * 0.28))),
    }


def responsive_image_label_class(Qt, QLabel, QPixmap, QSizePolicy):
    """Create a binding-neutral label class for crisp pixel-art scaling."""

    class ResponsiveImageLabel(QLabel):
        def __init__(self, image_path, vertical_policy=QSizePolicy.Expanding):
            super().__init__()
            self.source_pixmap = QPixmap(str(image_path))
            self.setAlignment(Qt.AlignCenter)
            self.setMinimumSize(1, 1)
            self.setSizePolicy(QSizePolicy.Ignored, vertical_policy)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            if self.source_pixmap.isNull():
                return
            available = self.contentsRect().size()
            if available.width() <= 0 or available.height() <= 0:
                return
            self.setPixmap(self.source_pixmap.scaled(
                available, Qt.KeepAspectRatio, Qt.FastTransformation
            ))

    return ResponsiveImageLabel


def configure_high_dpi(QApplication, Qt, binding):
    """Enable device-independent Qt 5 scaling before QApplication exists."""
    if binding != "PySide2":
        return
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    set_rounding_policy = getattr(
        QApplication, "setHighDpiScaleFactorRoundingPolicy", None
    )
    policy_enum = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    pass_through = (
        getattr(policy_enum, "PassThrough", None)
        if policy_enum is not None else None
    )
    if pass_through is None:
        pass_through = getattr(Qt, "PassThrough", None)
    if set_rounding_policy is not None and pass_through is not None:
        set_rounding_policy(pass_through)


def configure_responsive_window(
    window, QApplication, minimum_size=(640, 480), default_size=(760, 560),
    maximum_size=(920, 680), screen_ratio=(0.72, 0.78),
):
    """Size a wizard from the usable screen with safe compact fallbacks."""
    screen = QApplication.primaryScreen()
    if screen is None:
        window.setMinimumSize(*minimum_size)
        window.resize(*default_size)
        return default_size
    available = screen.availableGeometry()
    minimum_width = min(minimum_size[0], max(480, available.width() - 40))
    minimum_height = min(minimum_size[1], max(400, available.height() - 40))
    width = max(minimum_width, min(
        maximum_size[0], round(available.width() * screen_ratio[0])
    ))
    height = max(minimum_height, min(
        maximum_size[1], round(available.height() * screen_ratio[1])
    ))
    window.setMinimumSize(minimum_width, minimum_height)
    window.resize(width, height)
    return width, height


def add_wizard_button(
    QPushButton, layout, text, callback, primary=False,
    minimum_size=(100, 30),
):
    """Create and append a consistently configured wizard button."""
    button = QPushButton(text)
    button.setMinimumSize(*minimum_size)
    if primary:
        button.setDefault(True)
    button.clicked.connect(callback)
    layout.addWidget(button)
    return button


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
    if profile["name"] == "standard" or os.environ.get("QT_STYLE_OVERRIDE"):
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
            applied = set_attribute(33, 2) or applied
            applied = set_attribute(38, 2) or applied
        return applied
    except (AttributeError, OSError, TypeError, ValueError):
        return False
