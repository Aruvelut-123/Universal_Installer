import unittest
from pathlib import Path

from platform_utils import (
    add_wizard_button,
    configure_high_dpi,
    configure_responsive_window,
    responsive_image_label_class,
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
    def test_sidebar_label_expands_inside_its_layout(self):
        source = (Path(__file__).parents[1] / "main.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "self.left_layout.addWidget(self.character_label, 1)", source
        )
        self.assertNotIn(
            "self.left_layout.setAlignment(Qt.AlignCenter)", source
        )

    def test_responsive_image_is_set_before_first_resize(self):
        class Size:
            def width(self):
                return 1

            def height(self):
                return 1

        class Rectangle:
            def size(self):
                return Size()

        class Label:
            def __init__(self):
                self.pixmap = None

            def setAlignment(self, value):
                pass

            def setMinimumSize(self, *size):
                pass

            def setSizePolicy(self, *policy):
                pass

            def contentsRect(self):
                return Rectangle()

            def setPixmap(self, pixmap):
                self.pixmap = pixmap

        class Pixmap:
            def __init__(self, path):
                self.path = path

            def isNull(self):
                return False

        qt = type("Qt", (), {
            "AlignCenter": 1,
            "KeepAspectRatio": 2,
            "FastTransformation": 3,
        })
        size_policy = type("SizePolicy", (), {
            "Expanding": 1,
            "Ignored": 2,
        })
        image_label = responsive_image_label_class(
            qt, Label, Pixmap, size_policy
        )("sidebar.png")

        self.assertIs(image_label.pixmap, image_label.source_pixmap)

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
