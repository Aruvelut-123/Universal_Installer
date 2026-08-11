import unittest

from linux_display import configure_linux_qt_platform


class LinuxDisplayTests(unittest.TestCase):
    def test_wayland_session_uses_native_backend_with_x11_fallback(self):
        environment = {
            "XDG_SESSION_TYPE": "wayland",
            "WAYLAND_DISPLAY": "wayland-0",
            "DISPLAY": ":0",
        }

        self.assertEqual(
            configure_linux_qt_platform(environment, "Linux"),
            "wayland;xcb",
        )
        self.assertEqual(environment["QT_QPA_PLATFORM"], "wayland;xcb")

    def test_x11_session_uses_xcb(self):
        environment = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
        self.assertEqual(
            configure_linux_qt_platform(environment, "Linux"), "xcb"
        )

    def test_explicit_platform_is_preserved(self):
        environment = {
            "QT_QPA_PLATFORM": "offscreen",
            "WAYLAND_DISPLAY": "wayland-0",
        }
        self.assertEqual(
            configure_linux_qt_platform(environment, "Linux"), "offscreen"
        )

    def test_headless_and_non_linux_environments_are_unchanged(self):
        headless = {}
        windows = {"DISPLAY": ":0"}
        self.assertIsNone(configure_linux_qt_platform(headless, "Linux"))
        self.assertIsNone(configure_linux_qt_platform(windows, "Windows"))
        self.assertNotIn("QT_QPA_PLATFORM", headless)
        self.assertNotIn("QT_QPA_PLATFORM", windows)
