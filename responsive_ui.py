"""Shared responsive Qt helpers for the installer and uninstaller."""

from __future__ import annotations


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
