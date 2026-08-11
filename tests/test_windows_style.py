import unittest
from unittest import mock

from windows_style import configure_windows_qt_style, windows_style_profile


class WindowsStyleTests(unittest.TestCase):
    def test_windows_generations_receive_distinct_profiles(self):
        windows7 = windows_style_profile((6, 1, 7601), "Windows")
        windows8 = windows_style_profile((6, 3, 9600), "Windows")
        windows10 = windows_style_profile((10, 0, 19045), "Windows")
        windows11 = windows_style_profile((10, 0, 26100), "Windows")

        self.assertEqual(windows7["name"], "windows7")
        self.assertEqual(windows8["name"], "windows8")
        self.assertEqual(windows10["name"], "windows10")
        self.assertEqual(windows11["name"], "windows11")
        self.assertTrue(windows11["mica"])

    def test_non_windows_profile_does_not_enable_native_effects(self):
        profile = windows_style_profile((10, 0, 26100), "Linux")
        self.assertEqual(profile["name"], "standard")
        self.assertFalse(profile["mica"])

    def test_explicit_qt_style_override_is_preserved(self):
        application = mock.Mock()
        with mock.patch.dict(
            "os.environ", {"QT_STYLE_OVERRIDE": "fusion"}, clear=True
        ):
            profile = configure_windows_qt_style(
                application, (10, 0, 26100), "Windows"
            )
        self.assertEqual(profile["name"], "windows11")
        application.setStyle.assert_not_called()
