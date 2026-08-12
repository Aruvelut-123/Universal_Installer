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
