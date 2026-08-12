import unittest

from responsive_ui import (
    add_wizard_button,
    configure_high_dpi,
    configure_responsive_window,
)


class FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class FakeButton:
    def __init__(self, text):
        self.text = text
        self.clicked = FakeSignal()
        self.minimum_size = None
        self.default = False

    def setMinimumSize(self, *size):
        self.minimum_size = size

    def setDefault(self, value):
        self.default = value


class FakeLayout:
    def __init__(self):
        self.widgets = []

    def addWidget(self, widget):
        self.widgets.append(widget)


class FakeWindow:
    def __init__(self):
        self.minimum_size = None
        self.size = None

    def setMinimumSize(self, *size):
        self.minimum_size = size

    def resize(self, *size):
        self.size = size


class ResponsiveUiTests(unittest.TestCase):
    def test_wizard_button_applies_shared_defaults(self):
        layout = FakeLayout()
        callback = object()

        button = add_wizard_button(
            FakeButton, layout, "Next", callback, primary=True
        )

        self.assertEqual(button.minimum_size, (100, 30))
        self.assertTrue(button.default)
        self.assertIs(button.clicked.callback, callback)
        self.assertEqual(layout.widgets, [button])

    def test_responsive_window_uses_fallback_without_screen(self):
        window = FakeWindow()
        application = type(
            "Application", (), {"primaryScreen": staticmethod(lambda: None)}
        )

        size = configure_responsive_window(window, application)

        self.assertEqual(size, (760, 560))
        self.assertEqual(window.minimum_size, (640, 480))
        self.assertEqual(window.size, size)

    def test_high_dpi_is_only_configured_for_qt5(self):
        class Application:
            attributes = []

            @classmethod
            def setAttribute(cls, value, enabled=True):
                cls.attributes.append((value, enabled))

        qt = type("Qt", (), {
            "AA_EnableHighDpiScaling": 1,
            "AA_UseHighDpiPixmaps": 2,
        })

        configure_high_dpi(Application, qt, "PySide6")
        self.assertEqual(Application.attributes, [])
        configure_high_dpi(Application, qt, "PySide2")
        self.assertEqual(Application.attributes, [(1, True), (2, True)])


if __name__ == "__main__":
    unittest.main()
