from __future__ import annotations

import atexit
import json
import os
import platform
import re
import stat
import subprocess
import sys
import shutil
import ctypes
import bz2
import gzip
import lzma
import zipfile
import rarfile
import py7zr
import tarfile
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import traceback
from typing import Any

from uninstaller import (
    INSTALL_DATA_DIRECTORY,
    INSTALL_MANIFEST_NAME,
    InstallRecorder,
    installed_component_versions,
    load_manifest,
    register_windows_uninstaller,
    remove_windows_uninstall_entry,
)

try:
    from typing import override
except ImportError:
    def override(method):
        """Python 3.8-compatible no-op replacement for typing.override."""
        return method


def is_frozen_application() -> bool:
    """Return whether the process is running from a frozen executable."""
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def resolve_application_directory() -> Path:
    """Locate external assets beside the source file or compiled executable."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        appimage_path = Path(appimage).resolve()
        if appimage_path.is_file():
            return appimage_path.parent

    launch_file = sys.executable if is_frozen_application() else __file__
    directory = Path(launch_file).resolve().parent
    for parent in (directory, *directory.parents):
        if parent.suffix.lower() == ".app":
            return parent.parent
    return directory


APPLICATION_DIR = resolve_application_directory()
os.chdir(APPLICATION_DIR)

# ============ REDIRECT STDOUT/STDERR TO FILES ============
class TeeLogger:
    """Writes to both original stdout/stderr and log files"""
    def __init__(self, filename, mode='a', original_stream=None):
        self.original_stream = original_stream
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = APPLICATION_DIR / "logs" / f"{filename}_{timestamp}.log"
        self.mode = mode
        self.file = None
        
    def write(self, message):
        if self.file is None:
            try:
                self.filename.parent.mkdir(parents=True, exist_ok=True)
                self.file = open(self.filename, self.mode, encoding='utf-8')
            except OSError as error:
                if self.original_stream:
                    self.original_stream.write(f"Failed to create log file: {error}\n")
                    self.original_stream.write(message)
                    self.original_stream.flush()
                return
        
        # Write to file
        try:
            self.file.write(message)
            self.file.flush()
        except (OSError, ValueError):
            pass
        
        # Also write to original stream (console)
        if self.original_stream:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except (OSError, ValueError):
                pass
    
    def flush(self):
        try:
            if self.file:
                self.file.flush()
        except (OSError, ValueError):
            pass
        if self.original_stream:
            try:
                self.original_stream.flush()
            except (OSError, ValueError):
                pass
    
    def close(self):
        try:
            if self.file:
                self.file.close()
                self.file = None
        except (OSError, ValueError):
            pass

# Save original stdout/stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Redirect stdout to output.log
sys.stdout = TeeLogger("output", 'w', original_stdout)

# Redirect stderr to debug.log
sys.stderr = TeeLogger("debug", 'w', original_stderr)
atexit.register(sys.stdout.close)
atexit.register(sys.stderr.close)

# Also capture unhandled exceptions to debug.log
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Write uncaught exceptions to debug.log"""
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    sys.stderr.write(f"\n{'='*80}\n")
    sys.stderr.write(f"UNCAUGHT EXCEPTION at {datetime.now()}\n")
    sys.stderr.write(f"{'='*80}\n")
    sys.stderr.write(error_msg)
    sys.stderr.write(f"{'='*80}\n")
    sys.stderr.flush()
    
    # Also print to original stderr
    if original_stderr:
        original_stderr.write(error_msg)
    
    # Call original handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = global_exception_handler

# Log startup information
print("=" * 80)
print(f"Application started at {datetime.now()}")
print(f"Python version: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"System: {platform.system()}")
print(f"Working directory: {os.getcwd()}")
print(f"Command line: {' '.join(sys.argv)}")
print(f"Process ID: {os.getpid()}")
print("=" * 80)
print("Found app directory: ", APPLICATION_DIR)

try:
    from PySide6.QtWidgets import (
        QAbstractItemView, QApplication, QMainWindow, QWidget, QStackedWidget,
        QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QCheckBox,
        QLineEdit, QFileDialog, QProgressBar, QGroupBox, QFrame, QMessageBox,
        QTreeWidget, QTreeWidgetItem,
    )
    from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QPixmap
    from PySide6.QtCore import Qt, QThread, Signal
    QT_BINDING = "PySide6"
except ImportError:
    from PySide2.QtWidgets import (
        QAbstractItemView, QApplication, QMainWindow, QWidget, QStackedWidget,
        QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QCheckBox,
        QLineEdit, QFileDialog, QProgressBar, QGroupBox, QFrame, QMessageBox,
        QTreeWidget, QTreeWidgetItem,
    )
    from PySide2.QtGui import QColor, QFont, QIcon, QPalette, QPixmap
    from PySide2.QtCore import Qt, QThread, Signal
    QT_BINDING = "PySide2"

print(f"Qt binding: {QT_BINDING}")
installer_metadata: dict[str, Any] | None = None

INSTALLER_METADATA_ALIASES = {
    "product_name": "short_name",
    "publisher": "author",
    "requires_admin": "need_admin",
    "includes_uninstaller": "has_uninstaller",
    "core_component_index": "main_item",
    "component_metadata_file": "item_metadata",
    "product_registry_key": "registry_key",
    "footer_text": "footer_info",
    "license_path": "license_file",
    "sidebar_image": "left_pic",
    "header_image": "header_pic",
    "icon_file": "icon",
    "directory_title": "select_directory_title",
    "directory_help": "select_directory_tip",
}

COMPONENT_METADATA_ALIASES = {
    "display_name": "name",
    "component_id": "id",
    "selected_by_default": "checked",
    "partially_selected_by_default": "part_checked",
    "description": "desc",
    "parent_component": "after",
    "common_files": "files",
    "windows_x86_files": "winx86file",
    "windows_x64_files": "winx64file",
    "windows_arm64_files": "winarm64file",
    "linux_x86_files": "linuxx86file",
    "linux_x64_files": "linuxx64file",
    "linux_arm64_files": "linuxarm64file",
    "macos_files": "macfile",
    "generic_x86_files": "x86file",
    "generic_x64_files": "x64file",
    "destinations": "actions",
    "default_install_path": "default_path",
    "default_linux_install_path": "default_path_linux",
    "default_macos_install_path": "default_path_macos",
}


def configure_high_dpi() -> None:
    """Enable device-independent Qt 5 scaling before QApplication exists."""
    if QT_BINDING != "PySide2":
        return

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    set_rounding_policy = getattr(
        QApplication, "setHighDpiScaleFactorRoundingPolicy", None
    )
    policy_enum = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    pass_through = (
        getattr(policy_enum, "PassThrough", None)
        if policy_enum is not None
        else None
    )
    if pass_through is None:
        pass_through = getattr(Qt, "PassThrough", None)
    if set_rounding_policy is not None and pass_through is not None:
        set_rounding_policy(pass_through)

REQUIRED_INSTALLER_METADATA = {
    "program_name", "short_name", "version",
    "author", "has_uninstaller", "need_admin", "main_item",
    "item_metadata", "registry_key", "uninstall_registry_key",
    "footer_info", "license_file",
    "left_pic", "header_pic", "icon",
}

def get_installer_metadata() -> dict:
    global installer_metadata
    if installer_metadata is not None:
        return installer_metadata
    try:
        with (APPLICATION_DIR / "metadata.json").open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取 metadata.json: {error}") from error

    if not isinstance(data, dict):
        raise ValueError("metadata.json 的顶层必须是对象")
    data = dict(data)
    for readable_key, internal_key in INSTALLER_METADATA_ALIASES.items():
        if internal_key not in data and readable_key in data:
            data[internal_key] = data[readable_key]
    missing = REQUIRED_INSTALLER_METADATA - data.keys()
    if missing:
        raise ValueError(f"metadata.json 缺少字段: {', '.join(sorted(missing))}")
    expected_types = {
        "program_name": str,
        "short_name": str,
        "version": str,
        "need_admin": bool,
        "has_uninstaller": bool,
        "main_item": int,
        "item_metadata": str,
        "registry_key": str,
        "uninstall_registry_key": str,
    }
    invalid_types = [
        key
        for key, expected_type in expected_types.items()
        if type(data[key]) is not expected_type
    ]
    if invalid_types:
        raise ValueError(
            f"metadata.json 字段类型错误: {', '.join(invalid_types)}"
        )
    installer_metadata = data
    return installer_metadata

# 全局常量
INSTALLER_METADATA = get_installer_metadata()
PROGRAM_NAME: str = INSTALLER_METADATA["program_name"]
VERSION: str = INSTALLER_METADATA["version"]
REGISTRY_KEY: str = INSTALLER_METADATA["registry_key"]
UNINSTALL_REG_KEY: str = INSTALLER_METADATA["uninstall_registry_key"]
DEFAULT_WINDOW_SIZE = (760, 560)
MINIMUM_WINDOW_SIZE = (640, 480)
METADATA_PATH: str = INSTALLER_METADATA["item_metadata"]
MAIN_ITEM: int = INSTALLER_METADATA["main_item"]

metadata: dict[str, Any] | None = None


def get_metadata() -> dict:
    global metadata
    if metadata is not None:
        return metadata

    metadata_path = APPLICATION_DIR / Path(METADATA_PATH.replace("\\", "/"))
    try:
        with metadata_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取组件配置 {metadata_path}: {error}") from error

    if isinstance(data, dict) and "items" not in data and "components" in data:
        data = dict(data)
        data["items"] = data["components"]
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"{metadata_path} 必须包含 components 数组")
    if not data["items"]:
        raise ValueError(f"{metadata_path} 的 components 不能为空")

    normalized_items = []
    for raw_item in data["items"]:
        if not isinstance(raw_item, dict):
            normalized_items.append(raw_item)
            continue
        item = dict(raw_item)
        for readable_key, internal_key in COMPONENT_METADATA_ALIASES.items():
            if internal_key not in item and readable_key in item:
                item[internal_key] = item[readable_key]
        normalized_items.append(item)
    data["items"] = normalized_items

    if INSTALLER_METADATA["has_uninstaller"]:
        uninstaller = data.get("uninstaller")
        if not isinstance(uninstaller, dict):
            raise ValueError(f"{metadata_path} 缺少 uninstaller 对象")
        for system_name in ("windows", "linux", "darwin"):
            configuration = uninstaller.get(system_name)
            if not isinstance(configuration, dict):
                raise ValueError(
                    f"{metadata_path} 的 uninstaller.{system_name} 必须是对象"
                )
            configuration = dict(configuration)
            if "file" not in configuration and "source_file" in configuration:
                configuration["file"] = configuration["source_file"]
            if (
                "executable" not in configuration
                and "installed_executable" in configuration
            ):
                configuration["executable"] = configuration["installed_executable"]
            uninstaller[system_name] = configuration
            invalid_fields = [
                field
                for field in ("file", "executable")
                if not isinstance(configuration.get(field), str)
                or not configuration[field].strip()
            ]
            if invalid_fields:
                raise ValueError(
                    f"{metadata_path} 的 uninstaller.{system_name} 字段无效: "
                    f"{', '.join(invalid_fields)}"
                )
            executable_parts = configuration["executable"].replace("\\", "/").split("/")
            if (
                configuration["executable"].startswith(("/", "\\"))
                or re.match(r"^[A-Za-z]:", configuration["executable"])
                or ".." in executable_parts
            ):
                raise ValueError(
                    f"{metadata_path} 的 uninstaller.{system_name}.executable "
                    "必须是安装目录内的相对路径"
                )

    item_ids = [item.get("id") for item in data["items"] if isinstance(item, dict)]
    if len(item_ids) != len(data["items"]) or any(
        not isinstance(item_id, str) or not item_id.strip()
        for item_id in item_ids
    ):
        raise ValueError(f"{metadata_path} 中每个组件都必须是带 id 的对象")
    if len(item_ids) != len(set(item_ids)):
        raise ValueError(f"{metadata_path} 中存在重复组件 id")
    known_ids = set(item_ids)
    file_keys = (
        "files", "winx86file", "winx64file", "winarm64file",
        "linuxx86file", "linuxx64file", "linuxarm64file", "macfile",
        "x86file", "x64file",
    )
    for item in data["items"]:
        component_id = item["id"]
        expected_item_types = {
            "name": str,
            "required": bool,
            "checked": bool,
            "dependencies": list,
        }
        invalid_fields = [
            key
            for key, expected_type in expected_item_types.items()
            if key not in item or type(item[key]) is not expected_type
        ]
        if invalid_fields:
            raise ValueError(
                f"组件 {component_id} 缺少字段或字段类型错误: "
                f"{', '.join(invalid_fields)}"
            )
        if any(
            not isinstance(dependency_id, str)
            for dependency_id in item["dependencies"]
        ):
            raise ValueError(f"组件 {component_id} 的 dependencies 只能包含字符串")
        for key in file_keys:
            files = item.get(key)
            if files is not None and (
                not isinstance(files, list)
                or any(not isinstance(file_name, str) for file_name in files)
            ):
                raise ValueError(f"组件 {component_id} 的 {key} 必须是字符串数组或 null")
        if item.get("actions") is not None and not isinstance(item["actions"], dict):
            raise ValueError(f"组件 {component_id} 的 actions 必须是对象或 null")
        uninstall_directories = item.get("remove_directories_on_uninstall", [])
        if not isinstance(uninstall_directories, list) or any(
            not isinstance(value, str) or not value.strip()
            for value in uninstall_directories
        ):
            raise ValueError(
                f"组件 {component_id} 的 remove_directories_on_uninstall "
                "必须是非空字符串数组"
            )
        for value in uninstall_directories:
            normalized = value.replace("\\", "/")
            without_placeholder = normalized.replace("{install_path}", "")
            parts = [part for part in without_placeholder.split("/") if part]
            if (
                ".." in parts
                or not parts
                or (
                    "{install_path}" not in normalized
                    and (normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized))
                )
            ):
                raise ValueError(
                    f"组件 {component_id} 的卸载目录必须是安装目录内的相对路径: "
                    f"{value}"
                )
        missing_dependencies = set(item.get("dependencies", [])) - known_ids
        if missing_dependencies:
            raise ValueError(
                f"组件 {component_id} 引用了不存在的依赖: "
                f"{', '.join(sorted(missing_dependencies))}"
            )
        parent_id = item.get("after")
        if parent_id is not None and parent_id not in known_ids:
            raise ValueError(f"组件 {component_id} 的 after 指向不存在的组件 {parent_id}")
        configured_files = [
            file_name
            for key in file_keys
            for file_name in (item.get(key) or [])
        ]
        if configured_files and (
            not isinstance(item.get("version"), str)
            or not item["version"].strip()
        ):
            raise ValueError(
                f"包含安装文件的组件 {component_id} 必须具有非空 version"
            )
        actions = item.get("actions") or {}
        missing_actions = set(configured_files) - actions.keys()
        if missing_actions:
            raise ValueError(
                f"组件 {component_id} 缺少 actions: "
                f"{', '.join(sorted(missing_actions))}"
            )

    if INSTALLER_METADATA["has_uninstaller"]:
        current_configuration = data["uninstaller"].get(platform.system().lower())
        if current_configuration:
            payload = current_configuration["file"]
            payload_is_required = any(
                item.get("required")
                and payload in get_component_files(item)
                and payload in (item.get("actions") or {})
                for item in data["items"]
            )
            if not payload_is_required:
                raise ValueError(
                    f"当前平台卸载器 {payload} 必须属于带 actions 的必选组件"
                )

    dependency_graph = {
        item["id"]: item.get("dependencies", []) for item in data["items"]
    }
    visiting = set()
    visited = set()

    def visit(component_id):
        if component_id in visiting:
            raise ValueError(f"组件依赖存在循环: {component_id}")
        if component_id in visited:
            return
        visiting.add(component_id)
        for dependency_id in dependency_graph[component_id]:
            visit(dependency_id)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in dependency_graph:
        visit(component_id)

    if not 0 <= MAIN_ITEM < len(data["items"]):
        raise ValueError(f"main_item={MAIN_ITEM} 超出 items 范围")
    metadata = data
    return metadata

THEME_COLORS = {
    "light": {
        "window": "#F5F5F5",
        "base": "#FFFFFF",
        "alternate": "#F0F0F0",
        "text": "#202020",
        "muted": "#666666",
        "border": "#C8C8C8",
        "button": "#F1F1F1",
        "button_hover": "#E5E5E5",
        "button_pressed": "#D9D9D9",
        "disabled": "#A0A0A0",
        "highlight": "#4BA348",
        "highlight_hover": "#3D8C39",
        "highlight_pressed": "#2D6C29",
        "highlight_text": "#FFFFFF",
        "log_background": "#FAFAFA",
    },
    "dark": {
        "window": "#202124",
        "base": "#292A2D",
        "alternate": "#303134",
        "text": "#F1F3F4",
        "muted": "#B0B3B8",
        "border": "#5F6368",
        "button": "#35363A",
        "button_hover": "#45464B",
        "button_pressed": "#2A2B2E",
        "disabled": "#80868B",
        "highlight": "#57B957",
        "highlight_hover": "#66C766",
        "highlight_pressed": "#3F9340",
        "highlight_text": "#FFFFFF",
        "log_background": "#17181A",
    },
}


def get_system_theme() -> str:
    """Return the OS application theme, with a Windows registry fallback."""
    app = QApplication.instance()
    if app is not None:
        style_hints = app.styleHints()
        if hasattr(style_hints, "colorScheme"):
            scheme = style_hints.colorScheme()
            color_scheme = getattr(Qt, "ColorScheme", None)
            if color_scheme is not None:
                if scheme == color_scheme.Dark:
                    return "dark"
                if scheme == color_scheme.Light:
                    return "light"

    if platform.system().lower() == "windows":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value else "dark"
        except (ImportError, OSError):
            pass
    return "light"


def create_theme_palette(theme: str) -> QPalette:
    """Build a complete Qt palette for the requested theme."""
    colors = THEME_COLORS[theme]
    palette = QPalette()
    roles = {
        QPalette.Window: "window",
        QPalette.WindowText: "text",
        QPalette.Base: "base",
        QPalette.AlternateBase: "alternate",
        QPalette.ToolTipBase: "base",
        QPalette.ToolTipText: "text",
        QPalette.Text: "text",
        QPalette.Button: "button",
        QPalette.ButtonText: "text",
        QPalette.BrightText: "highlight_text",
        QPalette.Link: "highlight",
        QPalette.Highlight: "highlight",
        QPalette.HighlightedText: "highlight_text",
        QPalette.PlaceholderText: "muted",
    }
    for role, color_name in roles.items():
        palette.setColor(role, QColor(colors[color_name]))
    palette.setColor(
        QPalette.Disabled,
        QPalette.Text,
        QColor(colors["disabled"]),
    )
    palette.setColor(
        QPalette.Disabled,
        QPalette.ButtonText,
        QColor(colors["disabled"]),
    )
    return palette


def create_theme_stylesheet(theme: str) -> str:
    """Return palette-aware QSS without hard-coded light-only widget styles."""
    color = THEME_COLORS[theme]
    return f"""
        QMainWindow, QWidget {{
            background-color: {color['window']};
            color: {color['text']};
        }}
        QGroupBox {{
            border: 1px solid {color['border']};
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        QLineEdit, QTextEdit, QTreeWidget {{
            background-color: {color['base']};
            color: {color['text']};
            border: 1px solid {color['border']};
            border-radius: 3px;
            selection-background-color: {color['highlight']};
            selection-color: {color['highlight_text']};
        }}
        QPushButton {{
            background-color: {color['button']};
            color: {color['text']};
            border: 1px solid {color['border']};
            border-radius: 3px;
            padding: 5px 15px;
        }}
        QPushButton:hover {{ background-color: {color['button_hover']}; }}
        QPushButton:pressed {{ background-color: {color['button_pressed']}; }}
        QPushButton:disabled {{ color: {color['disabled']}; }}
        QPushButton[buttonStyle="primary"] {{
            background-color: {color['highlight']};
            color: {color['highlight_text']};
            border-color: {color['highlight_pressed']};
        }}
        QPushButton[buttonStyle="primary"]:hover {{
            background-color: {color['highlight_hover']};
        }}
        QPushButton[buttonStyle="primary"]:pressed {{
            background-color: {color['highlight_pressed']};
        }}
        QProgressBar {{
            background-color: {color['base']};
            color: {color['text']};
            border: 1px solid {color['border']};
            border-radius: 5px;
            text-align: center;
        }}
        QProgressBar::chunk {{ background-color: {color['highlight']}; }}
        QTextEdit[logView="true"] {{
            background-color: {color['log_background']};
            color: {color['text']};
        }}
        QLabel[muted="true"] {{ color: {color['muted']}; }}
        QMenuBar, QMenu {{
            background-color: {color['window']};
            color: {color['text']};
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background-color: {color['highlight']};
            color: {color['highlight_text']};
        }}
    """


def apply_application_theme(theme: str) -> None:
    """Apply a theme to the active application and all existing widgets."""
    if theme not in THEME_COLORS:
        raise ValueError(f"未知主题: {theme}")
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication 尚未创建")
    app.setPalette(create_theme_palette(theme))
    app.setStyleSheet(create_theme_stylesheet(theme))


def get_application_icon() -> QIcon:
    """Load the configured icon from the application directory."""
    icon_path = APPLICATION_DIR / Path(INSTALLER_METADATA["icon"].replace("\\", "/"))
    icon = QIcon(str(icon_path))
    if icon.isNull():
        print(f"[WARN] 无法加载应用图标: {icon_path}")
    return icon


@contextmanager
def blocked_signals(widget):
    """Block widget signals temporarily on both Qt 5 and Qt 6."""
    previous_state = widget.blockSignals(True)
    try:
        yield
    finally:
        widget.blockSignals(previous_state)


def configure_windows_app_id() -> None:
    """Give the packaged app its own Windows taskbar identity."""
    if platform.system().lower() != "windows":
        return
    app_id = ".".join(
        part.strip().replace(" ", "_")
        for part in (
            INSTALLER_METADATA["author"],
            REGISTRY_KEY.replace("\\", "."),
            PROGRAM_NAME,
        )
        if part.strip()
    )
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError) as error:
        print(f"[WARN] 无法设置 Windows AppUserModelID: {error}")


def format_size(size: int) -> str:
    """Format a byte count using binary units."""
    value = float(max(size, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024


def get_windows_native_machine(environment=None) -> str:
    """Return the native Windows architecture, including under WOW64."""
    environment = os.environ if environment is None else environment
    return (
        environment.get("PROCESSOR_ARCHITEW6432")
        or environment.get("PROCESSOR_ARCHITECTURE")
        or platform.machine()
    ).lower()


def get_platform_file_candidates(
    system=None, machine=None, environment=None
) -> tuple[str, ...]:
    """Return platform file keys in preferred-to-compatible order."""
    system = (system or platform.system()).lower()
    if machine is None and system == "windows":
        machine = get_windows_native_machine(environment)
    else:
        machine = machine or platform.machine()
    machine = machine.lower()
    architecture = {
        "amd64": "x64", "x86_64": "x64", "x64": "x64",
        "i386": "x86", "i686": "x86", "x86": "x86",
        "arm64": "arm64", "aarch64": "arm64",
    }.get(machine)
    if system == "darwin":
        return ("macfile",)
    if system not in {"windows", "linux"} or architecture is None:
        return ()

    prefix = "win" if system == "windows" else "linux"
    compatibility = {
        "arm64": ("arm64", "x64", "x86"),
        "x64": ("x64", "x86"),
        "x86": ("x86",),
    }[architecture]
    return tuple(f"{prefix}{candidate}file" for candidate in compatibility)


def get_component_files(item: dict) -> list[str]:
    """Return common files plus the best available platform-specific set."""
    files = list(item.get("files") or [])
    for key in get_platform_file_candidates():
        platform_files = item.get(key)
        if platform_files:
            files.extend(platform_files)
            break
    return files


def get_uninstaller_configuration() -> dict:
    """Return and validate the uninstaller payload for the current OS."""
    if not INSTALLER_METADATA["has_uninstaller"]:
        return {}
    system = platform.system().lower()
    configuration = get_metadata()["uninstaller"].get(system)
    if not configuration:
        raise ValueError(f"当前操作系统没有卸载器配置: {system}")
    return dict(configuration)


def get_default_install_path(item: dict) -> str:
    key = {
        "windows": "default_path",
        "linux": "default_path_linux",
        "darwin": "default_path_macos",
    }.get(platform.system().lower())
    return item.get(key, "") if key else ""


COMPAT_INSTALL_PATH_ENV_VARS = (
    "STEAM_COMPAT_INSTALL_PATH",
    "GAMEHUB_GAME_PATH",
    "WINLATOR_GAME_PATH",
)
COMPAT_PREFIX_ENV_VARS = (
    "WINEPREFIX",
    "STEAM_COMPAT_DATA_PATH",
    "PROTON_PREFIX",
)


def unique_paths(paths) -> list[Path]:
    """Deduplicate paths without requiring them to exist."""
    result = []
    seen = set()
    for path in paths:
        path = Path(path)
        key = os.path.normcase(os.path.normpath(str(path)))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def runtime_path_candidates(raw_path, system=None) -> list[Path]:
    """Translate host paths exposed by Proton/Wine into accessible paths."""
    if not raw_path:
        return []
    system = (system or platform.system()).lower()
    expanded = os.path.expandvars(os.path.expanduser(str(raw_path).strip().strip('"')))
    if system == "windows" and expanded.startswith("/"):
        # Wine, Proton, Winlator and GameHub usually expose the host root as Z:.
        candidates = [
            Path("Z:" + expanded.replace("/", "\\")),
            Path(expanded),
        ]
    else:
        candidates = [Path(expanded)]
    return unique_paths(candidates)


def get_windows_drive_roots() -> list[Path]:
    """Return mounted Windows drives, including Wine/Android mapped drives."""
    if platform.system().lower() != "windows":
        return []
    if hasattr(os, "listdrives"):
        drive_names = os.listdrives()
    else:
        drive_names = [f"{letter}:\\" for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ"]
    return [
        Path(drive)
        for drive in drive_names
        if drive and drive[0].upper() not in {"A", "B"} and Path(drive).is_dir()
    ]


def steam_library_paths(steam_roots, system=None) -> list[Path]:
    """Read every Steam library, retaining the primary library as a fallback."""
    import vdf

    libraries = []
    for steam_root in unique_paths(steam_roots):
        if steam_root.is_dir():
            libraries.append(steam_root)
        library_file = steam_root / "steamapps" / "libraryfolders.vdf"
        if not library_file.is_file():
            continue
        try:
            with library_file.open("r", encoding="utf-8", errors="ignore") as file:
                data = vdf.load(file)
        except (OSError, ValueError, SyntaxError) as error:
            print(f"读取 Steam 库配置失败 {library_file}: {error}")
            continue
        entries = data.get("libraryfolders", {})
        if not isinstance(entries, dict):
            continue
        for key, value in entries.items():
            if not str(key).isdigit() or not isinstance(value, dict):
                continue
            for path in runtime_path_candidates(value.get("path"), system):
                if path.is_dir():
                    libraries.append(path)
    return unique_paths(libraries)


def expected_game_executables(installer_data: dict) -> tuple[str, ...]:
    """Get optional executable hints, falling back to the directory prompt."""
    configured = installer_data.get("game_executables")
    if configured is None:
        configured = installer_data.get("game_executable")
    if isinstance(configured, str):
        names = [configured]
    elif isinstance(configured, list):
        names = [name for name in configured if isinstance(name, str)]
    else:
        names = []
    title = installer_data.get("select_directory_title", "")
    names.extend(re.findall(r"[A-Za-z0-9_.+-]+\.exe\b", title, flags=re.IGNORECASE))
    return tuple(dict.fromkeys(Path(name).name for name in names if name.strip()))


def game_path_candidates(root: Path, game_name: str) -> list[Path]:
    """Return bounded common layouts used by Steam and Android containers."""
    return [
        root / game_name,
        root / "Games" / game_name,
        root / "games" / game_name,
        root / "Winlator" / "Games" / game_name,
        root / "GameHub" / "Games" / game_name,
        root / "steamapps" / "common" / game_name,
        root / "SteamLibrary" / "steamapps" / "common" / game_name,
        root / "Program Files (x86)" / "Steam" / "steamapps" / "common" / game_name,
        root / "Program Files" / "Steam" / "steamapps" / "common" / game_name,
    ]


def root_contains_game(root: Path, executable_names) -> bool:
    """Recognize a container drive that maps directly to the game directory."""
    if not root.is_dir():
        return False
    return any((root / executable).is_file() for executable in executable_names)


def find_game_under_roots(roots, game_name: str, executable_names=()) -> Path | None:
    """Search only known shallow layouts; never recursively walk whole drives."""
    for root in unique_paths(roots):
        if root_contains_game(root, executable_names):
            return root
        for candidate in game_path_candidates(root, game_name):
            if candidate.is_dir():
                return candidate
    return None


def compatibility_prefixes(steam_libraries, game_id, environment=None) -> list[Path]:
    """Collect Wine and Proton prefixes relevant to the configured game."""
    if environment is None:
        environment = os.environ
    prefixes = []
    for variable in COMPAT_PREFIX_ENV_VARS:
        for path in runtime_path_candidates(environment.get(variable)):
            prefixes.extend((path, path / "pfx"))
    if platform.system().lower() != "windows":
        prefixes.append(Path.home() / ".wine")
    if game_id:
        for library in steam_libraries:
            prefixes.append(
                library / "steamapps" / "compatdata" / str(game_id) / "pfx"
            )
    return unique_paths(path for path in prefixes if path.is_dir())


def prefix_drive_roots(prefixes) -> list[Path]:
    """Expose C: and custom dosdevices mappings from Wine/Proton prefixes."""
    roots = []
    for prefix in unique_paths(prefixes):
        for candidate in (prefix, prefix / "drive_c", prefix / "pfx" / "drive_c"):
            if candidate.name.lower() == "drive_c" and candidate.is_dir():
                roots.append(candidate)
        for dosdevices in (prefix / "dosdevices", prefix / "pfx" / "dosdevices"):
            if not dosdevices.is_dir():
                continue
            try:
                mappings = list(dosdevices.iterdir())
            except OSError:
                continue
            for mapping in mappings:
                if re.fullmatch(r"[a-zA-Z]:", mapping.name) and mapping.is_dir():
                    try:
                        roots.append(mapping.resolve())
                    except OSError:
                        roots.append(mapping)
    return unique_paths(roots)


def relaunch_as_admin() -> None:
    """Relaunch source or compiled Windows application with elevation."""
    if platform.system().lower() != "windows":
        return
    arguments = list(sys.argv[1:])
    if not is_frozen_application():
        arguments.insert(0, str(Path(__file__).resolve()))
    parameters = subprocess.list2cmdline(arguments)
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        parameters,
        str(APPLICATION_DIR),
        1,
    )
    if result <= 32:
        raise OSError(f"请求管理员权限失败，ShellExecuteW 返回 {result}")

# 检查管理员权限的函数
def is_admin():
    try:
        if platform.system().lower() == "windows":
            return ctypes.windll.shell32.IsUserAnAdmin()
        return True
    except (AttributeError, OSError):
        return False

# 安装线程
class InstallThread(QThread):
    progress_updated = Signal(int, str)
    finished = Signal(bool)

    def __init__(self, path, components):
        super().__init__()
        self.path = path
        self.components = components
        self.items_by_id = {
            item["id"]: item for item in get_metadata()["items"]
        }
        self.success = False
        self.recorder = None
        print(f"[DEBUG] InstallThread初始化: path={path}, components={components}")

    def _resolve_install_order(self):
        """Topologically order selected components and include dependencies."""
        selected = {
            component_id
            for component_id, enabled in self.components.items()
            if enabled
        }
        order = []
        visiting = set()
        visited = set()

        def visit(component_id):
            if component_id in visiting:
                raise ValueError(f"组件依赖存在循环: {component_id}")
            if component_id in visited:
                return
            item = self.items_by_id.get(component_id)
            if item is None:
                raise KeyError(f"组件不存在: {component_id}")
            visiting.add(component_id)
            for dependency_id in item.get("dependencies", []):
                selected.add(dependency_id)
                visit(dependency_id)
            visiting.remove(component_id)
            visited.add(component_id)
            order.append(component_id)

        for component_id in self.items_by_id:
            if component_id in selected:
                visit(component_id)
        return order

    @staticmethod
    def _get_platform_files_key():
        """根据当前平台和架构返回对应的文件键名"""
        candidates = get_platform_file_candidates()
        print(
            f"[DEBUG] 检测平台: system={platform.system().lower()}, "
            f"machine={platform.machine().lower()}, candidates={candidates}"
        )
        return candidates[0] if candidates else None

    def _get_file_info(self, file, item):
        """获取文件的目标路径和类型"""
        print(f"[DEBUG] 处理文件: {file}")
        
        if file not in item.get("actions", {}):
            print(f"[DEBUG] 文件 {file} 不在actions中，跳过")
            return None, None
        
        # 构建目标路径
        in_path = item["actions"][file]
        print(f"[DEBUG] 原始actions路径: {in_path}")
        in_path = in_path.replace("{install_path}", self.path)
        in_path = os.path.normpath(
            in_path.replace("\\", os.sep).replace("/", os.sep)
        )
        if not os.path.isabs(in_path):
            in_path = os.path.abspath(in_path)
        print(f"[DEBUG] 替换后的路径: {in_path}")
        
        # 获取文件类型
        file_type = self._get_file_type(file)
        print(f"[DEBUG] 文件类型: {file_type}")
        
        return in_path, file_type

    @staticmethod
    def _get_file_type(filename):
        """根据完整文件名返回受支持的文件类型。"""
        filename = filename.lower()
        suffix_map = {
            '.tar.bz2': 'tar',
            '.tar.gz': 'tar',
            '.tar.xz': 'tar',
            '.tbz2': 'tar',
            '.tgz': 'tar',
            '.txz': 'tar',
            '.tbz': 'tar',
            '.zip': 'zip',
            '.rar': 'rar',
            '.7z': '7z',
            '.tar': 'tar',
            '.bz2': 'bzip2',
            '.gz': 'gzip',
            '.xz': 'xz',
        }
        for suffix, file_type in suffix_map.items():
            if filename.endswith(suffix):
                return file_type
        return None

    @staticmethod
    def _validate_archive_members(member_names, destination):
        """Reject archive members that would escape the destination directory."""
        destination = os.path.realpath(destination)
        for member_name in member_names:
            normalized_name = member_name.replace("\\", "/")
            drive, _ = os.path.splitdrive(normalized_name)
            if drive or normalized_name.startswith("/"):
                raise ValueError(f"压缩包包含绝对路径: {member_name}")
            target = os.path.realpath(
                os.path.join(destination, *normalized_name.split("/"))
            )
            try:
                inside_destination = os.path.commonpath([destination, target]) == destination
            except ValueError:
                inside_destination = False
            if not inside_destination:
                raise ValueError(f"压缩包路径越界: {member_name}")

    def _install_extracted_tree(self, extracted_root, destination):
        """Merge an extracted payload and avoid rewriting identical files."""
        extracted_root = Path(extracted_root)
        destination = Path(destination)
        for current, directories, files in os.walk(str(extracted_root)):
            current_path = Path(current)
            relative = current_path.relative_to(extracted_root)
            target_directory = destination / relative
            self.recorder.prepare_directory(target_directory)
            for directory in directories:
                self.recorder.prepare_directory(target_directory / directory)
            for filename in files:
                source = current_path / filename
                if source.is_symlink():
                    raise ValueError(f"压缩包解压结果包含符号链接: {source}")
                target = target_directory / filename
                self.recorder.install_file(source, target)

    def _extract_archive(self, archive_name, archive_type, in_path):
        """Safely extract to a temporary tree, then transactionally merge it."""
        with tempfile.TemporaryDirectory(prefix="universal-installer-") as temporary:
            extract_path = Path(temporary)
            if archive_type == 'zip':
                with zipfile.ZipFile(archive_name, "r") as archive:
                    infos = archive.infolist()
                    self._validate_archive_members(
                        (info.filename for info in infos), str(extract_path)
                    )
                    for info in infos:
                        if stat.S_ISLNK(info.external_attr >> 16):
                            raise ValueError(f"ZIP 压缩包包含符号链接: {info.filename}")
                    archive.extractall(str(extract_path))
                    for info in infos:
                        mode = info.external_attr >> 16
                        if not info.is_dir() and mode & 0o111:
                            extracted = extract_path.joinpath(
                                *info.filename.replace("\\", "/").split("/")
                            )
                            extracted.chmod(extracted.stat().st_mode | (mode & 0o111))
            elif archive_type == 'rar':
                with rarfile.RarFile(archive_name, "r") as archive:
                    infos = archive.infolist()
                    self._validate_archive_members(
                        (info.filename for info in infos), str(extract_path)
                    )
                    for info in infos:
                        is_symlink = getattr(info, "is_symlink", None)
                        if is_symlink is not None and is_symlink():
                            raise ValueError(f"RAR 压缩包包含符号链接: {info.filename}")
                    archive.extractall(str(extract_path))
            elif archive_type == '7z':
                with py7zr.SevenZipFile(archive_name, "r") as archive:
                    entries = archive.list()
                    self._validate_archive_members(
                        (entry.filename for entry in entries), str(extract_path)
                    )
                    archive.extractall(str(extract_path))
            elif archive_type == 'tar':
                with tarfile.open(archive_name, "r:*") as archive:
                    members = archive.getmembers()
                    self._validate_archive_members(
                        (info.name for info in members), str(extract_path)
                    )
                    unsupported = [
                        info.name for info in members
                        if not (info.isfile() or info.isdir())
                    ]
                    if unsupported:
                        raise ValueError(
                            f"TAR 压缩包包含不支持的链接或设备: {unsupported[0]}"
                        )
                    archive.extractall(str(extract_path), members=members)
            elif archive_type in {'gzip', 'bzip2', 'xz'}:
                opener, suffix = {
                    'gzip': (gzip.open, '.gz'),
                    'bzip2': (bz2.open, '.bz2'),
                    'xz': (lzma.open, '.xz'),
                }[archive_type]
                output_name = os.path.basename(archive_name)[:-len(suffix)]
                if not output_name:
                    raise ValueError(f"无法确定解压后的文件名: {archive_name}")
                with opener(archive_name, 'rb') as source, (
                    extract_path / output_name
                ).open('wb') as target:
                    shutil.copyfileobj(source, target)
            else:
                raise ValueError(f"未知的压缩类型: {archive_type}")
            self._install_extracted_tree(extract_path, in_path)

    def _handle_file(self, file, item, is_platform_file=False):
        """统一处理单个文件"""
        print(f"[DEBUG] 处理文件: {file}, is_platform_file={is_platform_file}")
        
        # 获取文件信息
        in_path, file_type = self._get_file_info(file, item)
        if not in_path:
            print(f"[DEBUG] 无法获取目标路径，跳过: {file}")
            return

        # 规范化文件路径
        file_path = os.path.abspath(
            file.replace("\\", os.sep).replace("/", os.sep)
        )
        if file_type is None:
            destination = Path(in_path) / Path(file_path).name
            print(f"[DEBUG] 普通文件直接复制: {file_path} -> {destination}")
            self.recorder.install_file(file_path, destination)
            return

        print(f"[DEBUG] 调用run_extract: archive={file_path}, type={file_type}, in_path={in_path}")
        self.run_extract(file_path, file_type, in_path)

    def _process_files(self, files, item):
        """处理文件列表"""
        if not files:
            return
        
        print(f"[DEBUG] 处理文件列表: {files}")
        for file in files:
            self._handle_file(file, item)

    def _process_component(self, component):
        """处理单个组件"""
        print(f"[DEBUG] 开始安装组件: {component}")
        item = self.items_by_id.get(component)
        if item is None:
            raise KeyError(f"组件不存在: {component}")
        files = get_component_files(item)
        print(f"[DEBUG] 组件 {component} 文件列表: {files}")
        self._process_files(files, item)

    def run(self):
        print("[DEBUG] run()方法开始执行")
        registered_uninstaller = None
        try:
            # 0. 准备工作
            print("[DEBUG] 开始准备安装环境...")
            self.progress_updated.emit(5, "正在准备安装环境...")
            
            if not os.path.exists(self.path):
                print(f"[DEBUG] 路径不存在，创建目录: {self.path}")
                os.makedirs(self.path, exist_ok=True)
            else:
                print(f"[DEBUG] 路径已存在: {self.path}")

            print("[DEBUG] 准备工作完成，开始安装组件")
            
            # 2. 安装组件
            selected_components = self._resolve_install_order()
            total_components = len(selected_components)
            if total_components == 0:
                raise ValueError("没有可安装的组件")
            uninstaller_configuration = get_uninstaller_configuration()
            self.recorder = InstallRecorder(
                self.path,
                INSTALLER_METADATA,
                [self.items_by_id[component] for component in selected_components],
                uninstaller_configuration,
                core_component=get_metadata()["items"][MAIN_ITEM]["id"],
            )
            print(f"[DEBUG] 需要安装的组件数: {total_components}")

            for index, component in enumerate(selected_components, start=1):
                start_progress = 5 + int((index - 1) * 90 / total_components)
                print(
                    f"[DEBUG] 处理组件: {component}, "
                    f"进度: {index}/{total_components}"
                )
                self.progress_updated.emit(
                    start_progress, f"正在安装组件 {component}..."
                )
                self.recorder.begin_component(component)
                self._process_component(component)
                self.recorder.finish_component(component)

                completed_progress = 5 + int(index * 90 / total_components)
                self.progress_updated.emit(
                    completed_progress, f"组件 {component} 安装完成"
                )

            if uninstaller_configuration:
                uninstaller_path = (
                    Path(self.path).resolve()
                    / Path(uninstaller_configuration["executable"])
                )
                if not uninstaller_path.is_file():
                    raise FileNotFoundError(f"卸载程序安装失败: {uninstaller_path}")
                if platform.system().lower() != "windows":
                    uninstaller_path.chmod(uninstaller_path.stat().st_mode | 0o111)
                registered_uninstaller = register_windows_uninstaller(
                    INSTALLER_METADATA,
                    self.path,
                    uninstaller_path,
                    self.recorder.estimated_size(),
                )
                self.recorder.set_registry(registered_uninstaller)

            self.recorder.finalize()

            self.success = True
            print("[DEBUG] 所有组件安装成功")
            self.progress_updated.emit(100, "安装完成！")
            
        except Exception as e:
            print(f"[ERROR] 安装过程中发生异常: {e}")
            traceback.print_exc()
            self.progress_updated.emit(0, f"安装失败: {str(e)}")
            if registered_uninstaller:
                remove_windows_uninstall_entry(registered_uninstaller)
            if self.recorder is not None:
                self.recorder.rollback()
        finally:
            print(f"[DEBUG] run()方法结束，success={self.success}")
            self.finished.emit(self.success)

    def run_extract(self, archive_name, archive_type, in_path):
        print(f"[DEBUG] run_extract开始: archive_name={archive_name}, archive_type={archive_type}, in_path={in_path}")
        
        # 调用方可传相对或绝对路径；只规范化一次，避免重复拼接盘符。
        archive_name = os.path.abspath(
            archive_name.replace("\\", os.sep).replace("/", os.sep)
        )
        print(f"[DEBUG] 构建完整压缩包路径: {archive_name}")
        print(f"[DEBUG] 检查压缩包是否存在: {os.path.exists(archive_name)}")
        print(f"[DEBUG] 目标目录是否存在: {os.path.exists(in_path)}")

        if not os.path.isfile(archive_name):
            raise FileNotFoundError(f"压缩包不存在: {archive_name}")

        # 确保目标目录存在
        if not os.path.exists(in_path):
            print(f"[DEBUG] 目标目录不存在，创建: {in_path}")
        self.recorder.prepare_directory(in_path)
        
        self.progress_updated.emit(0, f"正在解压文件{archive_name}到{in_path}")
        
        try:
            print(f"[DEBUG] 开始解压，类型: {archive_type}")
            
            print(f"[DEBUG] 使用解压器: {archive_type}")
            self._extract_archive(archive_name, archive_type, in_path)
            print(f"[DEBUG] 解压完成: {archive_name}")
            
            print(f"[DEBUG] 解压成功: {archive_name} -> {in_path}")
            self.progress_updated.emit(0, f"解压成功: {archive_name}")
            
        except Exception as e:
            print(f"[ERROR] 解压失败: {e}")
            traceback.print_exc()
            raise

# 基础页面模板
class BasePage(QWidget):
    def __init__(self, parent, has_left_area=False, has_banner=True):
        super().__init__(parent)
        self.parent = parent

        if not Path(INSTALLER_METADATA["left_pic"]).is_file():
            has_left_area = False

        if not Path(INSTALLER_METADATA["header_pic"]).is_file():
            has_banner = False

        if has_banner:
            # 根布局 - 纵向布局
            self.root_layout = QVBoxLayout(self)
            self.root_layout.setContentsMargins(0, 0, 0, 0)
            self.root_layout.setSpacing(0)

            # 主布局 - 横向布局
            self.main_frame = QFrame()
            self.main_layout = QHBoxLayout(self.main_frame)
        else:
            self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        if has_left_area:
            # 左侧区域 - 卡通图片
            self.left_frame = QFrame()
            self.left_frame.setFixedWidth(200)
            self.left_layout = QVBoxLayout(self.left_frame)
            self.left_layout.setAlignment(Qt.AlignCenter)

            # 加载卡通图片
            self.character_label = QLabel()
            pixmap = QPixmap(get_installer_metadata()["left_pic"])
            if not pixmap.isNull():
                self.character_label.setPixmap(pixmap.scaled(170, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.character_label.setAlignment(Qt.AlignCenter)
            self.left_layout.addWidget(self.character_label)

        # 右侧区域 - 内容区域
        self.right_frame = QFrame()
        self.right_layout = QVBoxLayout(self.right_frame)
        self.right_layout.setContentsMargins(20, 20, 20, 20)
        self.right_layout.setSpacing(15)

        if has_banner:
            # 顶部区域 - 标题区域
            self.top_frame = QFrame()
            self.top_layout = QVBoxLayout(self.top_frame)

            # banner
            self.header = QLabel()
            pixmap = QPixmap(get_installer_metadata()["header_pic"])
            if not pixmap.isNull():
                self.header.setPixmap(
                    pixmap.scaled(150, 57, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            self.header.setAlignment(Qt.AlignLeft)

        # 添加标题
        self.title_label = QLabel()
        title_font = QFont("Microsoft YaHei UI", 12, QFont.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)

        # 副标题
        self.subtitle_label = QLabel()
        subtitle_font = QFont("Microsoft YaHei UI", 9)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)

        # 添加到布局
        if has_banner:
            self.top_layout.addWidget(self.header)
            self.top_layout.addWidget(self.title_label)
            self.top_layout.addWidget(self.subtitle_label)
        else:
            self.right_layout.addWidget(self.title_label)
            self.right_layout.addWidget(self.subtitle_label)

        # 添加内容区域
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(15)
        self.right_layout.addLayout(self.content_layout)

        # 添加按钮区域
        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(0, 15, 0, 0)
        self.button_layout.addStretch(1)

        # 底部信息
        self.footer_label = QLabel(get_installer_metadata()["footer_info"])
        footer_font = QFont("Microsoft YaHei UI", 8)
        self.footer_label.setFont(footer_font)
        self.footer_label.setProperty("muted", True)
        self.footer_label.setAlignment(Qt.AlignCenter)

        # 添加到布局
        self.right_layout.addLayout(self.button_layout)
        self.right_layout.addWidget(self.footer_label)

        # 添加左右区域到主布局
        if has_left_area:
            self.main_layout.addWidget(self.left_frame)
        self.main_layout.addWidget(self.right_frame)
        if has_banner:
            self.root_layout.addWidget(self.top_frame)
            self.root_layout.addWidget(self.main_frame)

        # 设置页面样式
        self.setup_ui()

    def setup_ui(self):
        pass

    def add_button(self, text, callback, style="default"):
        button = QPushButton(text)
        button_font = QFont("Microsoft YaHei UI", 9)
        button.setFont(button_font)
        button.setMinimumSize(100, 30)

        if style == "primary":
            button.setProperty("buttonStyle", "primary")

        button.clicked.connect(callback)
        self.button_layout.addWidget(button)
        return button


# 欢迎页面
class WelcomePage(BasePage):
    @override
    def __init__(self, *args: Any, default_path: str, **kwargs: Any):
        self.default_path = default_path
        super().__init__(*args, **kwargs)

    def setup_ui(self):
        self.title_label.setText(PROGRAM_NAME)
        self.subtitle_label.setText("感谢您选择 "+get_installer_metadata()["short_name"])

        # 添加内容
        content_text = get_installer_metadata()["short_name"]+"主要由 "+get_installer_metadata()["author"]+" 制作\n\n"
        if "qq_group" in get_installer_metadata(): content_text += "如有疑问可加群："+get_installer_metadata()["qq_group"]+"\n\n"
        content_text += "点击[下一步(N)]继续。"

        content_label = QLabel(content_text)
        content_label.setFont(QFont("Microsoft YaHei UI", 9))
        content_label.setAlignment(Qt.AlignCenter)
        content_label.setWordWrap(True)

        self.content_layout.addStretch(1)
        self.content_layout.addWidget(content_label)
        self.content_layout.addStretch(2)

        # 添加按钮
        self.add_button("取消(C)", self.on_cancel)
        self.next_button = self.add_button("下一步(N)", self.on_next, "primary")

    def on_cancel(self):
        self.parent.cancel_installation()

    def on_next(self):
        self.parent.go_to_page("license")


# 许可协议页面
class LicensePage(BasePage):
    def setup_ui(self):
        self.title_label.setText(PROGRAM_NAME)
        self.subtitle_label.setText("在安装 "+get_installer_metadata()["short_name"]+" 之前，请阅读许可证条款")

        # 创建许可证文本框
        license_group = QGroupBox("许可证协议")
        license_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        license_layout = QVBoxLayout(license_group)

        self.license_text = QTextEdit()
        self.license_text.setReadOnly(True)
        try:
            with open(get_installer_metadata()["license_file"], "r", encoding="utf-8") as f:
                self.license_text.setText(f.read())
        except OSError:
            self.license_text.setText("许可协议文件未找到。\n一般意味着此工具为 All Rights Reserved 协议。")

        # 添加提示文本
        tip_label = QLabel("要阅读协议的其余部分，请使用滚动条浏览。")
        tip_label.setStyleSheet("font-size: 9pt;")
        tip_label.setProperty("muted", True)

        # 添加协议接受选项
        self.agree_checkbox = QCheckBox("我接受许可证的条款")
        self.agree_checkbox.setStyleSheet("font-size: 9pt;")

        license_layout.addWidget(self.license_text)
        license_layout.addWidget(tip_label)
        license_layout.addWidget(self.agree_checkbox)

        self.content_layout.addWidget(license_group)

        # 添加按钮
        back_btn = self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("welcome"))
        self.agree_button = self.add_button("我接受(I)", self.on_accept, "primary")
        self.agree_button.setEnabled(False)
        self.add_button("取消(C)", self.on_cancel)

        # 连接信号
        self.agree_checkbox.stateChanged.connect(
            lambda: self.agree_button.setEnabled(self.agree_checkbox.isChecked())
        )

    def on_accept(self):
        if self.agree_checkbox.isChecked():
            self.parent.go_to_page("directory")

    def on_cancel(self):
        self.parent.cancel_installation()


# 组件选择页面
class ComponentsPage(BasePage):
    on_select_change_size = Signal(int)

    def setup_ui(self):
        self.title_label.setText(PROGRAM_NAME)
        self.subtitle_label.setText("选择你想安装的 "+get_installer_metadata()["short_name"]+" 功能组件")

        # 创建组件选择区
        components_group = QGroupBox()
        components_layout = QHBoxLayout(components_group)

        # 左侧 - 组件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        tip_label = QLabel("请勾选你想安装的组件，并取消勾选你不想安装的组件。")
        tip_label.setStyleSheet("font-size: 9pt; margin-bottom: 10px;")

        self.components_list = QTreeWidget()
        self.components_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.components_list.setHeaderHidden(True)
        self.components_list.setColumnCount(1)
        self.components_list.setMouseTracking(True)  # 启用鼠标跟踪
        items = get_metadata()["items"]
        self.items_by_id = {item["id"]: item for item in items}
        self.tree_items_by_id = {}
        self.base_labels_by_id = {}
        self.default_states_by_id = {}
        self.installed_versions = {}
        self.loaded_install_root = None
        self.archive_size_cache = {}
        self.has_missing_required_files = False

        # First create every node so parents may appear after their children in JSON.
        for item in items:
            tree_item = QTreeWidgetItem()
            tree_item.setData(0, Qt.UserRole, item["id"])
            self.tree_items_by_id[item["id"]] = tree_item

            missing_files = [
                file_name
                for file_name in get_component_files(item)
                if not os.path.isfile(
                    os.path.abspath(
                        file_name.replace("\\", os.sep).replace("/", os.sep)
                    )
                )
            ]
            if item.get("required"):
                label = f"{item['name']} (必选)"
                tree_item.setCheckState(0, Qt.Checked)
                tree_item.setFlags(
                    tree_item.flags() & ~Qt.ItemIsUserCheckable
                )
            else:
                label = item["name"]
                tree_item.setFlags(
                    tree_item.flags() | Qt.ItemIsUserCheckable
                )
                initial_state = (
                    Qt.PartiallyChecked
                    if item.get("part_checked")
                    else Qt.Checked
                    if item.get("checked")
                    else Qt.Unchecked
                )
                tree_item.setCheckState(0, initial_state)
            self.default_states_by_id[item["id"]] = tree_item.checkState(0)

            if missing_files:
                label = f"{item['name']} (未找到对应文件)"
                tree_item.setFlags(
                    tree_item.flags() & ~Qt.ItemIsEnabled
                )
                if item.get("required"):
                    self.has_missing_required_files = True
                else:
                    tree_item.setCheckState(0, Qt.Unchecked)
                print(
                    f"组件 {item['id']} 缺少文件: {', '.join(missing_files)}"
                )
            if item.get("disabled"):
                tree_item.setFlags(
                    tree_item.flags() & ~Qt.ItemIsEnabled
                )
            if item.get("version"):
                label = f"{label}  v{item['version']}"
            self.base_labels_by_id[item["id"]] = label
            tree_item.setText(0, label)

        # Then attach nodes by stable ID instead of fuzzy display-name lookup.
        for item in items:
            tree_item = self.tree_items_by_id[item["id"]]
            parent_id = item.get("after")
            if parent_id is None:
                self.components_list.addTopLevelItem(tree_item)
            else:
                self.tree_items_by_id[parent_id].addChild(tree_item)

        self.components_list.itemEntered.connect(self.on_item_hovered)
        self.components_list.itemClicked.connect(self.on_item_clicked)
        self.components_list.itemChanged.connect(self.on_item_changed)

        # 空间信息
        self.space_label = QLabel("所需空间: 0 MB")
        self.space_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin-top: 10px;")

        left_layout.addWidget(tip_label)
        left_layout.addWidget(self.components_list)
        left_layout.addWidget(self.space_label)

        # 右侧 - 组件描述
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        desc_label = QLabel("组件描述")
        desc_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin-bottom: 10px;")

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setText("将光标悬停在组件名称之上，即可显示它的功能描述。")

        right_layout.addWidget(desc_label)
        right_layout.addWidget(self.description_text)

        components_layout.addWidget(left_widget)
        components_layout.addWidget(right_widget, 2)

        self.content_layout.addWidget(components_group)

        # 添加按钮
        self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("directory"))
        self.next_button = self.add_button("下一步(N)", self.on_next, "primary")
        self.next_button.setEnabled(not self.has_missing_required_files)
        self.add_button("取消(C)", self.on_cancel)
        self.on_select_change_size.connect(self.on_select_change_size_method)
        self.synchronize_selection()

    def on_select_change_size_method(self, size:int):
        self.need_space = size
        self.space_label.setText(f"所需空间：{format_size(size)}")

    def iter_tree_items(self):
        stack = [
            self.components_list.topLevelItem(index)
            for index in reversed(range(self.components_list.topLevelItemCount()))
        ]
        while stack:
            item = stack.pop()
            yield item
            stack.extend(
                item.child(index)
                for index in reversed(range(item.childCount()))
            )

    def on_next(self):
        # 保存选择的组件
        self.parent.selected_components = {}
        for item in self.iter_tree_items():
            key = item.data(0, Qt.UserRole)
            state = item.checkState(0) == Qt.Checked
            self.parent.selected_components[key] = state

        self.parent.need_space = self.need_space
        directory_page = self.parent.pages["directory"]
        if not directory_page.has_sufficient_space(self.need_space):
            QMessageBox.warning(
                self,
                "空间不足",
                "所选游戏目录所在磁盘没有足够空间安装这些组件。",
            )
            self.parent.go_to_page("directory")
            return
        self.parent.go_to_page("install")

    def on_cancel(self):
        self.parent.cancel_installation()

    def on_item_hovered(self, item):
        component_key = item.data(0, Qt.UserRole)
        description = self.items_by_id.get(component_key, {}).get(
            "desc", "未找到描述"
        )
        version = self.items_by_id.get(component_key, {}).get("version")
        if component_key in self.installed_versions:
            installed_version = self.installed_versions[component_key]
            installed_text = installed_version or "未记录版本"
            description = f"<p><b>已安装版本:</b> {installed_text}</p>{description}"
        if version:
            description = f"<p><b>可安装版本:</b> {version}</p>{description}"

        # 更新描述文本
        self.description_text.setHtml(description)

    def load_installation_state(self, install_root):
        """Restore selections and versions recorded in the chosen game folder."""
        root = Path(install_root).resolve()
        if root == self.loaded_install_root:
            return bool(self.installed_versions)

        manifest_path = (
            root / INSTALL_DATA_DIRECTORY / INSTALL_MANIFEST_NAME
        )
        manifest = None
        if manifest_path.is_file():
            _, manifest = load_manifest(manifest_path)
        installed_versions = (
            installed_component_versions(manifest) if manifest else {}
        )

        self.loaded_install_root = root
        self.installed_versions = installed_versions
        with blocked_signals(self.components_list):
            for component_id, tree_item in self.tree_items_by_id.items():
                item = self.items_by_id[component_id]
                if not tree_item.flags() & Qt.ItemIsEnabled:
                    state = Qt.Checked if item.get("required") else Qt.Unchecked
                elif item.get("required"):
                    state = Qt.Checked
                elif manifest is not None:
                    state = (
                        Qt.Checked
                        if component_id in installed_versions
                        else Qt.Unchecked
                    )
                else:
                    state = self.default_states_by_id[component_id]
                tree_item.setCheckState(0, state)

                label = self.base_labels_by_id[component_id]
                if component_id in installed_versions:
                    installed_version = installed_versions[component_id]
                    available_version = item.get("version")
                    if (
                        installed_version
                        and available_version
                        and installed_version != available_version
                    ):
                        status = f"已安装 v{installed_version}，可更新"
                    elif installed_version:
                        status = f"已安装 v{installed_version}"
                    else:
                        status = "已安装"
                    label = f"{label}  ({status})"
                tree_item.setText(0, label)

        self.synchronize_selection()
        return manifest is not None

    def on_item_clicked(self, item, column):
        # 如果点击的是父项目，更新子项目的选择状态
        if item.childCount() > 0:
            with blocked_signals(self.components_list):
                stack = [item.child(index) for index in range(item.childCount())]
                while stack:
                    child = stack.pop()
                    if (
                        child.flags() & Qt.ItemIsEnabled
                        and child.flags() & Qt.ItemIsUserCheckable
                    ):
                        child.setCheckState(0, item.checkState(0))
                    stack.extend(
                        child.child(index) for index in range(child.childCount())
                    )
        self.synchronize_selection()

    def get_selected_components_sizes(self):
        total_size = 0
        for component in self.iter_tree_items():
            if component.checkState(0) != Qt.Checked:
                continue
            component_id = component.data(0, Qt.UserRole)
            for file_name in get_component_files(self.items_by_id[component_id]):
                total_size += self.get_file_installed_size(file_name)
        return total_size

    def get_file_installed_size(self, file_name):
        path = os.path.abspath(
            file_name.replace("\\", os.sep).replace("/", os.sep)
        )
        try:
            stat = os.stat(path)
        except OSError as error:
            print(f"无法读取文件大小 {path}: {error}")
            return 0
        file_type = InstallThread._get_file_type(path)
        cache_key = (path, file_type, stat.st_size, stat.st_mtime_ns)
        if cache_key not in self.archive_size_cache:
            self.archive_size_cache[cache_key] = self.get_archive_size(
                path, file_type
            )
        return self.archive_size_cache[cache_key]

    @staticmethod
    def get_archive_size(file, file_type) -> int:
        file = os.path.abspath(file.replace("\\", os.sep).replace("/", os.sep))
        try:
            if file_type is None:
                return os.path.getsize(file)
            if file_type == "zip":
                with zipfile.ZipFile(file, 'r') as zip_ref:
                    return sum(info.file_size for info in zip_ref.infolist())
            if file_type == "rar":
                with rarfile.RarFile(file, 'r') as rar_ref:
                    return sum(f.file_size for f in rar_ref.infolist())
            if file_type == "7z":
                with py7zr.SevenZipFile(file, 'r') as sevenzip_ref:
                    return sum(
                        (getattr(info, 'uncompressed', 0) or 0)
                        for info in sevenzip_ref.list()
                        if not getattr(info, 'is_directory', False)
                    )
            if file_type == "tar":
                with tarfile.open(file, 'r:*') as tar_ref:
                    return sum(info.size for info in tar_ref.getmembers() if info.isfile())
            if file_type in {'gzip', 'bzip2', 'xz'}:
                opener = {
                    'gzip': gzip.open,
                    'bzip2': bz2.open,
                    'xz': lzma.open,
                }[file_type]
                with opener(file, 'rb') as archive:
                    return sum(
                        len(chunk)
                        for chunk in iter(lambda: archive.read(1024 * 1024), b'')
                    )
            raise NotImplementedError(f"不支持的压缩类型: {file_type}")
        except Exception as e:
            print(f"无法读取压缩包大小 {file}: {e}")
            return 0

    def find_component_by_id(self, component_id):
        return self.tree_items_by_id.get(component_id)

    @staticmethod
    def find_items_recursive(tree, text, column=0, match_flag=Qt.MatchContains):
        def search(items, results):
            for item in items:
                item_text = item.text(column)
                # Check for a match based on the specified flag
                if (
                        (match_flag == Qt.MatchContains and text in item_text) or
                        (match_flag == Qt.MatchExactly and item_text == text)
                ):
                    results.append(item)
                # Recursively search children
                if item.childCount() > 0:
                    search([item.child(i) for i in range(item.childCount())], results)

        results = []
        # Start search from top-level items
        search([tree.topLevelItem(i) for i in range(tree.topLevelItemCount())], results)
        return results

    def on_item_changed(self, item, column):
        self.synchronize_selection()

    def synchronize_selection(self):
        """Enforce dependency and parent-state invariants without signal recursion."""
        with blocked_signals(self.components_list):
            changed = True
            while changed:
                changed = False
                for component_id, tree_item in self.tree_items_by_id.items():
                    if tree_item.checkState(0) != Qt.Checked:
                        continue
                    for dependency_id in self.items_by_id[component_id].get(
                        "dependencies", []
                    ):
                        dependency = self.tree_items_by_id[dependency_id]
                        if dependency.checkState(0) != Qt.Checked:
                            dependency.setCheckState(0, Qt.Checked)
                            changed = True

            items_by_depth = sorted(
                self.tree_items_by_id.values(),
                key=lambda tree_item: self._tree_depth(tree_item),
                reverse=True,
            )
            for parent in items_by_depth:
                if parent.childCount() == 0:
                    continue
                states = [
                    parent.child(index).checkState(0)
                    for index in range(parent.childCount())
                ]
                if all(state == Qt.Checked for state in states):
                    parent.setCheckState(0, Qt.Checked)
                elif all(state == Qt.Unchecked for state in states):
                    parent.setCheckState(0, Qt.Unchecked)
                else:
                    parent.setCheckState(0, Qt.PartiallyChecked)

        self.on_select_change_size.emit(self.get_selected_components_sizes())

    @staticmethod
    def _tree_depth(item):
        depth = 0
        while item.parent() is not None:
            item = item.parent()
            depth += 1
        return depth

# 安装位置选择页面
class DirectoryPage(BasePage):
    def setup_ui(self):
        self.title_label.setText(PROGRAM_NAME)
        self.subtitle_label.setText("请选择安装路径")
        if "select_directory_title" in get_installer_metadata():
            self.subtitle_label.setText(get_installer_metadata()["select_directory_title"])

        # 添加路径选择区域
        path_group = QGroupBox()
        path_layout = QVBoxLayout(path_group)

        if "select_directory_tip" in get_installer_metadata():
            # 添加提示文本
            tip_label = QLabel(get_installer_metadata()["select_directory_tip"])
            tip_label.setStyleSheet("font-size: 9pt; color: #4BA348; margin-bottom: 10px;")
            path_layout.addWidget(tip_label)

        
        self.default_path = get_default_install_path(
            get_metadata()["items"][MAIN_ITEM]
        )

        # 路径选择框
        path_form = QHBoxLayout()
        self.path_input = QLineEdit(self.default_path)
        detect_btn = None
        if "is_steam_game" in get_installer_metadata():
            if get_installer_metadata()["is_steam_game"]:
                detect_btn = QPushButton("自动检测")
                detect_btn.setMinimumWidth(80)
                detect_btn.clicked.connect(self.update_directory)

        browse_btn = QPushButton("浏览...")
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self.browse_directory)

        path_form.addWidget(self.path_input)

        if "is_steam_game" in get_installer_metadata():
            if get_installer_metadata()["is_steam_game"]:
                if detect_btn is not None:
                    path_form.addWidget(detect_btn)

        path_form.addWidget(browse_btn)

        # 空间信息
        self.space_layout = QHBoxLayout()
        self.space_layout.addStretch(1)

        self.required_label = QLabel("所需空间: 0 KB")
        self.required_label.setStyleSheet("font-size: 9pt; margin: 5px;")

        self.available_label = QLabel()
        self.available_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin: 5px;")

        self.space_layout.addWidget(self.required_label)
        self.space_layout.addWidget(self.available_label)

        path_layout.addLayout(path_form)
        path_layout.addLayout(self.space_layout)

        self.content_layout.addWidget(path_group)

        # 更新空间信息
        self.update_disk_space()

        # 添加按钮
        self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("license"))
        self.next_button = self.add_button("下一步(N)", self.on_next, "primary")
        self.add_button("取消(C)", self.on_cancel)

        # 监听路径变化
        self.path_input.textChanged.connect(self.update_disk_space)
        
        self.parent.page_shown.connect(self.page_shown)

        self.update_directory()

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "浏览文件夹", self.path_input.text(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if directory:
            if any(ord(char) > 127 for char in directory):
                QMessageBox.warning(self, "路径错误", "安装路径不能包含中文字符！")
            else:
                self.path_input.setText(directory)

    def update_directory(self):
        path = self.detect_game_path()
        if path is not None:
            self.path_input.setText(path)
            self.update_disk_space()

    def detect_steam_path(self):
        """Backward-compatible alias for callers using the old method name."""
        return self.detect_game_path()

    def detect_game_path(self):
        game_name = INSTALLER_METADATA.get("game_name", "").strip()
        if not game_name:
            print("game name not contains in installer metadata, returning default path")
            return self.default_path
        if "/" in game_name or "\\" in game_name:
            print(f"拒绝包含路径分隔符的 game_name: {game_name}")
            return self.default_path

        executable_names = expected_game_executables(INSTALLER_METADATA)
        environment = os.environ

        # Proton provides the exact install path; custom container wrappers may
        # expose equivalent variables. Prefer these over all heuristic scans.
        for variable in COMPAT_INSTALL_PATH_ENV_VARS:
            for candidate in runtime_path_candidates(environment.get(variable)):
                if candidate.is_dir():
                    print(f"找到游戏目录 ({variable}): {candidate}")
                    return str(candidate)

        steam_roots = self.get_steam_paths()
        libraries = steam_library_paths(steam_roots)
        steam_game = find_game_under_roots(libraries, game_name)
        if steam_game is not None:
            print(f"找到游戏目录 (Steam/Proton): {steam_game}")
            return str(steam_game)

        prefixes = compatibility_prefixes(
            libraries,
            INSTALLER_METADATA.get("game_id"),
            environment,
        )
        prefix_game = find_game_under_roots(
            prefix_drive_roots(prefixes), game_name, executable_names
        )
        if prefix_game is not None:
            print(f"找到游戏目录 (Wine/Proton prefix): {prefix_game}")
            return str(prefix_game)

        # A Windows build running in Winlator or GameSir GameHub sees Android
        # storage through Wine drive mappings (commonly D:, E:, X: or Z:).
        mapped_game = find_game_under_roots(
            get_windows_drive_roots(), game_name, executable_names
        )
        if mapped_game is not None:
            print(f"找到游戏目录 (Winlator/GameHub mapped drive): {mapped_game}")
            return str(mapped_game)

        if self.default_path and Path(self.default_path).is_dir():
            print(f"使用已存在的默认目录: {self.default_path}")
        else:
            print("未找到 Steam/Wine/Proton/Winlator/GameHub 游戏目录")
        return self.default_path

    def get_steam_paths(self):
        """Return every accessible Steam root for native and compatibility environments."""
        os_name = platform.system().lower()
        paths = runtime_path_candidates(
            os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH"), os_name
        )

        if os_name == "windows":
            import winreg

            registry_locations = [
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam", ("SteamPath", "InstallPath"), 0),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", ("InstallPath",), winreg.KEY_WOW64_64KEY),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", ("InstallPath",), winreg.KEY_WOW64_32KEY),
            ]
            for hive, key_path, value_names, view in registry_locations:
                try:
                    with winreg.OpenKey(
                        hive, key_path, 0, winreg.KEY_READ | view
                    ) as key:
                        for value_name in value_names:
                            try:
                                path, _ = winreg.QueryValueEx(key, value_name)
                            except OSError:
                                continue
                            paths.extend(runtime_path_candidates(path, os_name))
                except OSError:
                    continue
            for drive in get_windows_drive_roots():
                paths.extend(
                    (
                        drive / "Steam",
                        drive / "SteamLibrary",
                        drive / "Program Files (x86)" / "Steam",
                        drive / "Program Files" / "Steam",
                    )
                )
        elif os_name == "linux":
            paths.extend(
                (
                    Path.home() / ".steam/root",
                    Path.home() / ".local/share/Steam",
                    Path.home() / ".steam/debian-installation",
                    Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
                    Path.home() / "snap/steam/common/.local/share/Steam",
                )
            )
        elif os_name == "darwin":
            paths.append(Path.home() / "Library/Application Support/Steam")

        existing_paths = []
        for path in unique_paths(paths):
            if not path.is_dir():
                continue
            try:
                path = path.resolve()
            except OSError:
                pass
            existing_paths.append(path)
            print(f"找到 Steam 根目录: {path}")
        if not existing_paths:
            print("未找到可访问的 Steam 根目录")
        return unique_paths(existing_paths)

    def get_steam_path(self):
        """Return the first Steam root for backward compatibility."""
        paths = self.get_steam_paths()
        return str(paths[0]) if paths else None

    def page_shown(self, name:str):
        if name == "directory":
            self.required_label.setText(
                f"所需空间：{format_size(self.parent.need_space)}"
            )

    def _get_mount_point(self, path):
        """获取路径所在的挂载点（Linux/macOS）"""
        import os
        
        path = os.path.abspath(path)
        while path != '/':
            if os.path.ismount(path):
                return path
            path = os.path.dirname(path)
        return '/'

    def update_disk_space(self):
        path = self.path_input.text()
        if path:
            try:
                existing_path = os.path.abspath(path)
                while not os.path.exists(existing_path):
                    parent_path = os.path.dirname(existing_path)
                    if parent_path == existing_path:
                        raise FileNotFoundError(path)
                    existing_path = parent_path
                usage = shutil.disk_usage(existing_path)
                self.available_label.setText(
                    f"可用空间: {format_size(usage.free)}"
                )
                enough_space = usage.free >= self.parent.need_space
                self.available_label.setStyleSheet(
                    "color: green; font-size: 9pt; font-weight: bold; margin: 5px;"
                    if enough_space
                    else "color: red; font-size: 9pt; font-weight: bold; margin: 5px;"
                )
                if hasattr(self, "next_button"):
                    self.next_button.setEnabled(enough_space)
            except OSError:
                self.available_label.setText("可用空间: 未知")
                self.available_label.setStyleSheet("color: palette(mid); font-size: 9pt;")

    def has_sufficient_space(self, required_space):
        path = self.path_input.text().strip()
        try:
            existing_path = os.path.abspath(path)
            while not os.path.exists(existing_path):
                parent_path = os.path.dirname(existing_path)
                if parent_path == existing_path:
                    return False
                existing_path = parent_path
            return shutil.disk_usage(existing_path).free >= required_space
        except OSError:
            return False

    def on_next(self):
        path = self.path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "路径错误", "请选择安装目录！")
            return

        if any(ord(char) > 127 for char in path):
            QMessageBox.warning(self, "路径错误", "安装路径不能包含中文字符！")
            return

        self.parent.install_path = str(Path(path).resolve())
        try:
            installed = self.parent.pages["components"].load_installation_state(
                self.parent.install_path
            )
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(
                self,
                "安装信息无效",
                f"无法读取该游戏目录中的现有安装信息：\n\n{error}",
            )
            return
        if installed:
            QMessageBox.information(
                self,
                "检测到现有安装",
                "已根据游戏目录中的安装信息勾选现有组件，并显示其版本。",
            )
        self.parent.go_to_page("components")

    def on_cancel(self):
        self.parent.cancel_installation()


# 安装过程页面
class InstallPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel(get_installer_metadata()["short_name"]+"安装")
        title_font = QFont("Microsoft YaHei UI", 12, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 副标题
        subtitle_label = QLabel("正在安装 "+get_installer_metadata()["short_name"]+" ，请稍候...")
        subtitle_label.setFont(QFont("Microsoft YaHei UI", 10))
        subtitle_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # 安装日志区域
        logs_group = QGroupBox("安装日志")
        logs_layout = QVBoxLayout(logs_group)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setProperty("logView", True)

        logs_layout.addWidget(self.log_area)
        main_layout.addWidget(logs_group)

        # 按钮区域
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch(1)

        # 显示详情按钮
        self.details_button = QPushButton("隐藏详情(D)")
        self.details_button.setFont(QFont("Microsoft YaHei UI", 9))
        self.details_button.clicked.connect(self.toggle_details)
        self.button_layout.addWidget(self.details_button)

        # 添加按钮
        self.next_button = self.add_button("下一步(F)", self.on_next, "primary")
        self.next_button.setEnabled(False)

        main_layout.addLayout(self.button_layout)

        # 底部信息
        footer_label = QLabel(get_installer_metadata()["footer_info"])
        footer_label.setFont(QFont("Microsoft YaHei UI", 8))
        footer_label.setProperty("muted", True)
        footer_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(footer_label)

        # 初始化时显示日志区域
        self.log_area_visible = True

    def add_button(self, text, callback, style="default"):
        button = QPushButton(text)
        button_font = QFont("Microsoft YaHei UI", 9)
        button.setFont(button_font)
        button.setMinimumSize(100, 30)

        if style == "primary":
            button.setProperty("buttonStyle", "primary")

        button.clicked.connect(callback)
        self.button_layout.addWidget(button)
        return button

    def start_installation(self, path, components):
        # 隐藏左侧图片区域
        #self.parent.right_frame.setFixedWidth(self.width())

        self.log_area.clear()
        self.log_area.append("开始安装...")

        self.thread = InstallThread(path, components)
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.finished.connect(self.installation_finished)
        self.thread.start()

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def installation_finished(self, success):
        self.parent.install_success = success
        if success:
            self.parent.go_to_page("finish")
        else:
            self.next_button.setText("查看结果(F)")
            self.next_button.setEnabled(True)

    def on_next(self):
        self.parent.go_to_page("finish")

    def toggle_details(self):
        self.log_area_visible = not self.log_area_visible
        self.log_area.setVisible(self.log_area_visible)
        if self.log_area_visible:
            self.details_button.setText("隐藏详情(D)")
        else:
            self.details_button.setText("显示详情(D)")


# 完成页面
class FinishPage(BasePage):
    def setup_ui(self):
        self.title_label.setText(PROGRAM_NAME)
        self.subtitle_label.setText("安装完成!")

        # 添加结果消息
        self.result_label = QLabel(get_installer_metadata()["short_name"]+" 已经成功安装到本机。")
        self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #4BA348;")
        self.result_label.setAlignment(Qt.AlignCenter)

        # 添加提示文本
        tip_label = QLabel("点击[完成(F)]关闭安装程序。")
        tip_label.setAlignment(Qt.AlignCenter)

        self.content_layout.addStretch(1)
        self.content_layout.addWidget(self.result_label)
        self.content_layout.addWidget(tip_label)

        # 添加按钮
        self.finish_button = self.add_button("完成(F)", self.on_finish, "primary")
        self.add_button("取消(C)", self.on_cancel)

    def set_result(self, success):
        if success:
            self.subtitle_label.setText("安装完成!")
            self.result_label.setText(get_installer_metadata()["short_name"]+" 已经成功安装到本机。")
            self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #4BA348;")
        else:
            self.subtitle_label.setText("安装失败")
            self.result_label.setText("安装失败，请检查错误信息后重试。")
            self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #FF0000;")

    def on_finish(self):
        self.parent.close()

    def on_cancel(self):
        self.parent.close()


# 主窗口
class InstallerWindow(QMainWindow):
    page_shown = Signal(str)
	
    def __init__(self):
        super().__init__()
        self.setWindowTitle(PROGRAM_NAME)
        self.setWindowIcon(get_application_icon())
        apply_application_theme(get_system_theme())
        self.setMinimumSize(*MINIMUM_WINDOW_SIZE)
        self.resize(*DEFAULT_WINDOW_SIZE)

        style_hints = QApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self.on_system_theme_changed)

        component_metadata = get_metadata()
        self.default_path = get_default_install_path(
            component_metadata["items"][MAIN_ITEM]
        )

        if INSTALLER_METADATA.get("need_admin") and not is_admin():
            relaunch_as_admin()
            sys.exit(0)

        # 创建堆栈窗口
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # 初始化安装数据
        self.install_path = ""
        self.selected_components = {}
        self.need_space = 0
        self.install_success = False

        # 初始化页面
        self.pages = {
            "welcome": WelcomePage(self, True, False, default_path=self.default_path),
            "license": LicensePage(self),
            "components": ComponentsPage(self),
            "directory": DirectoryPage(self),
            "install": InstallPage(self),
            "finish": FinishPage(self)
        }

        # 添加页面到堆栈
        for name, page in self.pages.items():
            self.stacked_widget.addWidget(page)

        # 设置当前页面
        self.go_to_page("welcome")

    def on_system_theme_changed(self, _color_scheme):
        apply_application_theme(get_system_theme())

    def go_to_page(self, page_name):
        self.page_shown.emit(page_name)
        self.stacked_widget.setCurrentWidget(self.pages[page_name])

        # 页面切换时的特殊处理
        if page_name == "finish":
            self.pages["finish"].set_result(self.install_success)
        elif page_name == "install":
            self.pages["install"].start_installation(
                self.install_path, self.selected_components
            )

    def cancel_installation(self):
        reply = QMessageBox.question(
            self, '退出安装',
            "您确定要退出 "+PROGRAM_NAME+" 吗?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.close()

    def closeEvent(self, event):
        install_page = getattr(self, "pages", {}).get("install")
        install_thread = (
            install_page.__dict__.get("thread")
            if install_page is not None
            else None
        )
        if install_thread is not None and install_thread.isRunning():
            QMessageBox.warning(
                self,
                "安装进行中",
                "文件仍在安装中，请等待安装完成后再关闭程序。",
            )
            event.ignore()
            return
        super().closeEvent(event)


def main():
    configure_windows_app_id()
    configure_high_dpi()
    app = QApplication(sys.argv)
    app.setApplicationName(PROGRAM_NAME)
    app.setApplicationDisplayName(PROGRAM_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName(INSTALLER_METADATA["author"])
    app.setWindowIcon(get_application_icon())
    app.setStyle("Fusion")

    # 设置应用程序字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    window = InstallerWindow()
    window.show()
    exec_method = getattr(app, "exec", None) or app.exec_
    sys.exit(exec_method())


if __name__ == "__main__":
    main()
