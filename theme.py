"""
WinUI 3-style theme with automatic dark/light mode detection.
Reads the Windows system theme preference and applies matching QSS.
"""
import sys


def is_dark_mode():
    """Detect whether Windows is using dark mode via registry."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0  # 0 = dark mode, 1 = light mode
    except Exception:
        return False  # Default to light mode


# ── WinUI 3 color tokens ──────────────────────────────────────────────

_LIGHT = {
    "bg":               "#F3F3F3",
    "surface":          "#FFFFFF",
    "surface_alt":      "#F9F9F9",
    "text":             "#1A1A1A",
    "text_secondary":   "#5D5D5D",
    "border":           "#E0E0E0",
    "accent":           "#0078D4",
    "accent_hover":     "#106EBE",
    "accent_pressed":   "#005A9E",
    "accent_text":      "#FFFFFF",
    "control_bg":       "#FFFFFF",
    "control_hover":    "#F5F5F5",
    "control_pressed":  "#EBEBEB",
    "control_border":   "#D1D1D1",
    "progress_bg":      "#E6E6E6",
    "progress_chunk":   "#0078D4",
    "success":          "#107C10",
    "error":            "#D13438",
    "tree_selection":   "#E0EEFA",
    "log_bg":           "#FAFAFA",
    "log_text":         "#1A1A1A",
    "scrollbar_bg":     "#F0F0F0",
    "scrollbar_handle": "#C2C2C2",
    "groupbox_title":   "#1A1A1A",
    "input_bg":         "#FFFFFF",
    "input_border":     "#D1D1D1",
    "checkbox_accent":  "#0078D4",
}

_DARK = {
    "bg":               "#202020",
    "surface":          "#2D2D2D",
    "surface_alt":      "#252525",
    "text":             "#FFFFFF",
    "text_secondary":   "#9E9E9E",
    "border":           "#3D3D3D",
    "accent":           "#60CDFF",
    "accent_hover":     "#4DB8E8",
    "accent_pressed":   "#3AA5D2",
    "accent_text":      "#003148",
    "control_bg":       "#3A3A3A",
    "control_hover":    "#454545",
    "control_pressed":  "#505050",
    "control_border":   "#4D4D4D",
    "progress_bg":      "#3A3A3A",
    "progress_chunk":   "#60CDFF",
    "success":          "#6CCB5F",
    "error":            "#FF6B6B",
    "tree_selection":   "#264F78",
    "log_bg":           "#1A1A1A",
    "log_text":         "#CCCCCC",
    "scrollbar_bg":     "#2A2A2A",
    "scrollbar_handle": "#5A5A5A",
    "groupbox_title":   "#FFFFFF",
    "input_bg":         "#3A3A3A",
    "input_border":     "#4D4D4D",
    "checkbox_accent":  "#60CDFF",
}


def get_palette(dark=None):
    """Return the color palette dict. Auto-detects if dark is None."""
    if dark is None:
        dark = is_dark_mode()
    return _DARK if dark else _LIGHT


def build_stylesheet(dark=None):
    """Build and return the full QSS stylesheet string."""
    c = get_palette(dark)

    return f"""
    /* ── Global ────────────────────────────────────────────── */
    QWidget {{
        background-color: {c['bg']};
        color: {c['text']};
        font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", sans-serif;
        font-size: 9pt;
    }}

    QMainWindow {{
        background-color: {c['bg']};
    }}

    /* ── Card surface (QFrame, QGroupBox) ──────────────────── */
    QFrame {{
        background-color: transparent;
        border: none;
    }}

    QGroupBox {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        color: {c['groupbox_title']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        color: {c['groupbox_title']};
    }}

    /* ── Buttons ───────────────────────────────────────────── */
    QPushButton {{
        background-color: {c['control_bg']};
        color: {c['text']};
        border: 1px solid {c['control_border']};
        border-radius: 4px;
        padding: 6px 20px;
        min-height: 20px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {c['control_hover']};
    }}
    QPushButton:pressed {{
        background-color: {c['control_pressed']};
    }}
    QPushButton:disabled {{
        opacity: 0.4;
        color: {c['text_secondary']};
    }}

    /* Primary (accent) button — applied via setProperty("class", "accent") */
    QPushButton[class="accent"] {{
        background-color: {c['accent']};
        color: {c['accent_text']};
        border: 1px solid {c['accent']};
        border-radius: 4px;
    }}
    QPushButton[class="accent"]:hover {{
        background-color: {c['accent_hover']};
        border-color: {c['accent_hover']};
    }}
    QPushButton[class="accent"]:pressed {{
        background-color: {c['accent_pressed']};
        border-color: {c['accent_pressed']};
    }}

    /* Danger button */
    QPushButton[class="danger"] {{
        background-color: {c['error']};
        color: #FFFFFF;
        border: 1px solid {c['error']};
        border-radius: 4px;
    }}
    QPushButton[class="danger"]:hover {{
        opacity: 0.85;
    }}

    /* ── Text input ────────────────────────────────────────── */
    QLineEdit {{
        background-color: {c['input_bg']};
        color: {c['text']};
        border: 1px solid {c['input_border']};
        border-bottom: 2px solid {c['accent']};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QLineEdit:focus {{
        border-bottom: 2px solid {c['accent']};
    }}

    /* ── Text area / QTextEdit ─────────────────────────────── */
    QTextEdit {{
        background-color: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 8px;
        selection-background-color: {c['accent']};
    }}

    /* Log area variant */
    QTextEdit[class="log"] {{
        background-color: {c['log_bg']};
        color: {c['log_text']};
        font-family: "Cascadia Code", "Consolas", monospace;
        border-radius: 6px;
    }}

    /* ── Labels ────────────────────────────────────────────── */
    QLabel {{
        background-color: transparent;
        color: {c['text']};
        border: none;
    }}
    QLabel[class="title"] {{
        font-size: 16pt;
        font-weight: 700;
    }}
    QLabel[class="subtitle"] {{
        font-size: 10pt;
        color: {c['text_secondary']};
    }}
    QLabel[class="footer"] {{
        font-size: 8pt;
        color: {c['text_secondary']};
    }}
    QLabel[class="success"] {{
        font-size: 10pt;
        font-weight: 600;
        color: {c['success']};
    }}
    QLabel[class="error"] {{
        font-size: 10pt;
        font-weight: 600;
        color: {c['error']};
    }}

    /* ── CheckBox ──────────────────────────────────────────── */
    QCheckBox {{
        spacing: 8px;
        color: {c['text']};
        background-color: transparent;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {c['control_border']};
        border-radius: 4px;
        background-color: {c['control_bg']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['checkbox_accent']};
        border-color: {c['checkbox_accent']};
    }}

    /* ── Progress bar ──────────────────────────────────────── */
    QProgressBar {{
        background-color: {c['progress_bg']};
        border: none;
        border-radius: 4px;
        text-align: center;
        min-height: 6px;
        max-height: 6px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: {c['progress_chunk']};
        border-radius: 4px;
    }}

    /* ── Tree widget ───────────────────────────────────────── */
    QTreeWidget {{
        background-color: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px;
        outline: none;
    }}
    QTreeWidget::item {{
        padding: 4px 2px;
        border-radius: 4px;
    }}
    QTreeWidget::item:hover {{
        background-color: {c['control_hover']};
    }}
    QTreeWidget::item:selected {{
        background-color: {c['tree_selection']};
    }}
    QTreeWidget::branch {{
        background-color: transparent;
    }}

    QHeaderView::section {{
        background-color: {c['surface']};
        color: {c['text']};
        border: none;
        padding: 4px 8px;
    }}

    /* ── Scrollbar ─────────────────────────────────────────── */
    QScrollBar:vertical {{
        background-color: {c['scrollbar_bg']};
        width: 8px;
        margin: 0;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c['scrollbar_handle']};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background-color: {c['scrollbar_bg']};
        height: 8px;
        margin: 0;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {c['scrollbar_handle']};
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ── QMessageBox ───────────────────────────────────────── */
    QMessageBox {{
        background-color: {c['surface']};
    }}
    QMessageBox QLabel {{
        color: {c['text']};
    }}

    /* ── QFileDialog / QDialog ─────────────────────────────── */
    QDialog {{
        background-color: {c['bg']};
    }}
    """


def apply_theme(app, dark=None):
    """Apply the WinUI 3 theme to a QApplication instance."""
    if dark is None:
        dark = is_dark_mode()
    app.setStyleSheet(build_stylesheet(dark))
