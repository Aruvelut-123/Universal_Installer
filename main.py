import json
import os
import platform
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
from datetime import datetime
import traceback

# ============ REDIRECT STDOUT/STDERR TO FILES ============
class TeeLogger:
    """Writes to both original stdout/stderr and log files"""
    def __init__(self, filename, mode='a', original_stream=None):
        self.original_stream = original_stream
        self.filename = filename
        self.mode = mode
        self.file = None
        
    def write(self, message):
        if self.file is None:
            try:
                # Create logs directory
                log_dir = "logs"
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                
                # Create file with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.filename = os.path.join(log_dir, f"{self.filename}_{timestamp}.log")
                self.file = open(self.filename, self.mode, encoding='utf-8')
            except Exception as e:
                print(f"Failed to create log file: {e}")
                return
        
        # Write to file
        try:
            self.file.write(message)
            self.file.flush()
        except:
            pass
        
        # Also write to original stream (console)
        if self.original_stream:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except:
                pass
    
    def flush(self):
        try:
            if self.file:
                self.file.flush()
        except:
            pass
        if self.original_stream:
            try:
                self.original_stream.flush()
            except:
                pass
    
    def close(self):
        try:
            if self.file:
                self.file.close()
                self.file = None
        except:
            pass

# Save original stdout/stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Create log files with timestamps
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Redirect stdout to output.log
sys.stdout = TeeLogger(f"output_{timestamp}", 'w', original_stdout)

# Redirect stderr to debug.log
sys.stderr = TeeLogger(f"debug_{timestamp}", 'w', original_stderr)

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
if platform.system().lower() == "darwin":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("=" * 80)
print(f"Application started at {datetime.now()}")
print(f"Python version: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"System: {platform.system()}")
print(f"Working directory: {os.getcwd()}")
print(f"Command line: {' '.join(sys.argv)}")
print(f"Process ID: {os.getpid()}")
print("=" * 80)
# Switch CWD immediately so every relative path below this line Just Works
if ".app" in os.getcwd():
    print("Found .app folder, going up three folders")
    os.chdir("../../..")
else:
    os.chdir(os.getcwd())
print("Found app directory: ", os.getcwd())

from typing import override, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QCheckBox, QLineEdit, QFileDialog,
    QProgressBar, QGroupBox, QFrame, QMessageBox, QTreeWidget,
    QTreeWidgetItem
)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QIcon, QPalette, QPixmap
)
from PySide6.QtCore import QSettings, QSize, Qt, QThread, Signal
metadata : dict = {}
installer_metadata : dict = {}

def get_installer_metadata() -> dict:
    global installer_metadata
    if installer_metadata != {}:
        return installer_metadata
    try:
        with open("metadata.json", "r", encoding='utf-8') as file:
            f = json.load(file)
            if "program_name" in f:
                if "short_name" in f:
                    if "version" in f:
                        if "is_release" in f:
                            if "password" in f:
                                if "has_uninstaller" in f:
                                    if "main_item" in f:
                                        if "item_metadata" in f:
                                            if "registry_key_name" in f:
                                                if "uninstall_registry_key_name" in f:
                                                    if "footer_info" in f:
                                                        if "license_file" in f:
                                                            if "left_pic" in f:
                                                                if "header_pic" in f:
                                                                    if "icon" in f:
                                                                        installer_metadata = f
                                                                        return f
            print("Metadata file not complete! continue with risks!")
            installer_metadata = f
            return f
    except Exception as e:
        print(e)
        installer_metadata = {}
        return {}

def get_metadata() -> dict:
    global metadata
    if metadata != {}:
        return metadata
    try:
        temp = METADATA_PATH.split("\\")
        rpath = os.getcwd()
        for path in temp:
            rpath = os.path.join(rpath, path)
        with open(rpath, "r", encoding='utf-8') as file:
            metadata = json.load(file)
            return metadata
    except Exception as e:
        print(e)
        return {}

# 全局常量
PROGRAM_NAME : str = get_installer_metadata()["program_name"]
VERSION : str = get_installer_metadata()["version"]
IS_RELEASE : bool = get_installer_metadata()["is_release"]
PASSWORD : str = get_installer_metadata()["password"]
REGISTRY_KEY : str = "Software\\"+get_installer_metadata()["registry_key_name"]
UNINSTALL_REG_KEY : str = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"+get_installer_metadata()["uninstall_registry_key_name"]
WINDOW_SIZE = (640, 480)  # 固定窗口大小
METADATA_PATH : str = get_installer_metadata()["item_metadata"]
MAIN_ITEM : int = get_installer_metadata()["main_item"]

THEME_MODES = {
    "system": "跟随系统",
    "light": "浅色",
    "dark": "深色",
}

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
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
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
        QPalette.ColorRole.Window: "window",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "base",
        QPalette.ColorRole.AlternateBase: "alternate",
        QPalette.ColorRole.ToolTipBase: "base",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "button",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.BrightText: "highlight_text",
        QPalette.ColorRole.Link: "highlight",
        QPalette.ColorRole.Highlight: "highlight",
        QPalette.ColorRole.HighlightedText: "highlight_text",
        QPalette.ColorRole.PlaceholderText: "muted",
    }
    for role, color_name in roles.items():
        palette.setColor(role, QColor(colors[color_name]))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(colors["disabled"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
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

# 检查管理员权限的函数
def is_admin():
    try:
        if platform.system().lower() == "windows":
            return ctypes.windll.shell32.IsUserAnAdmin()
        else:
            return True
    except:
        return False

# 安装线程
class InstallThread(QThread):
    progress_updated = Signal(int, str)
    finished = Signal(bool)

    def __init__(self, path, components):
        super().__init__()
        self.path = path
        self.components = components
        self.success = False
        print(f"[DEBUG] InstallThread初始化: path={path}, components={components}")

    def _get_platform_files_key(self):
        """根据当前平台和架构返回对应的文件键名"""
        system = platform.system().lower()
        machine = platform.machine()
        
        print(f"[DEBUG] 检测平台: system={system}, machine={machine}")
        
        platform_map = {
            'windows': {
                'AMD64': 'winx64file',
                'x86': 'winx86file'
            },
            'linux': {
                'x86_64': 'linuxx64file',
                'i386': 'linuxx86file'
            },
            'darwin': {
                'default': 'macfile'
            }
        }
        
        if system in platform_map:
            if system == 'darwin':
                return 'macfile'
            return platform_map[system].get(machine)
        
        print(f"[DEBUG] 不支持的平台: {system}/{machine}")
        return None

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
        in_path = in_path.replace("/", "\\")
        print(f"[DEBUG] 替换后的路径: {in_path}")
        
        # 非Windows系统
        if platform.system().lower() != "windows":
            # 使用os.path.join规范化路径
            temp = in_path.split("\\")
            in_path = os.path.join(*temp)  # 更简洁的方式
            print(f"[DEBUG] os.path.join后的路径: {in_path}")
        
            # 添加前缀
            in_path = "/" + in_path
            print(f"[DEBUG] 非Windows系统，添加前缀: {in_path}")
        
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
    def _extract_archive(archive_name, archive_type, in_path):
        """解压文件并确保压缩包句柄及时关闭。"""
        if archive_type == 'zip':
            with zipfile.ZipFile(archive_name, "r") as archive:
                archive.extractall(in_path)
        elif archive_type == 'rar':
            with rarfile.RarFile(archive_name, "r") as archive:
                archive.extractall(in_path)
        elif archive_type == '7z':
            with py7zr.SevenZipFile(archive_name, "r") as archive:
                archive.extractall(in_path)
        elif archive_type == 'tar':
            with tarfile.open(archive_name, "r:*") as archive:
                archive.extractall(in_path)
        elif archive_type in {'gzip', 'bzip2', 'xz'}:
            opener, suffix = {
                'gzip': (gzip.open, '.gz'),
                'bzip2': (bz2.open, '.bz2'),
                'xz': (lzma.open, '.xz'),
            }[archive_type]
            output_name = os.path.basename(archive_name)[:-len(suffix)]
            if not output_name:
                raise ValueError(f"无法确定解压后的文件名: {archive_name}")
            output_path = os.path.join(in_path, output_name)
            with opener(archive_name, 'rb') as source, open(output_path, 'wb') as target:
                shutil.copyfileobj(source, target)
        else:
            raise ValueError(f"未知的压缩类型: {archive_type}")

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
            os.makedirs(in_path, exist_ok=True)
            print(f"[DEBUG] 普通文件直接复制: {file_path} -> {in_path}")
            shutil.copy2(file_path, in_path)
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
        
        metadata = get_metadata()
        print(f"[DEBUG] 获取到元数据，items数量: {len(metadata['items']) if metadata else 0}")
        
        for item in metadata["items"]:
            if item["id"] != component:
                continue
                
            print(f"[DEBUG] 找到匹配的组件: {component}")
            
            # 1. 处理通用文件
            if item.get("files"):
                print(f"[DEBUG] 组件 {component} 有通用文件列表: {item['files']}")
                self._process_files(item["files"], item)
            
            # 2. 处理平台特定文件
            platform_key = self._get_platform_files_key()
            if platform_key and platform_key in item:
                print(f"[DEBUG] 处理平台特定文件: {platform_key}")
                self._process_files(item[platform_key], item)
            
            # 如果平台特定文件找不到，尝试查找替代方案
            elif platform_key:
                # Windows可能同时有32位和64位，尝试另一个
                if platform.system().lower() == "windows":
                    alt_key = 'winx86file' if platform_key == 'winx64file' else 'winx64file'
                    if alt_key in item:
                        print(f"[DEBUG] 尝试使用替代架构: {alt_key}")
                        self._process_files(item[alt_key], item)
                # Linux类似
                elif platform.system().lower() == "linux":
                    alt_key = 'linuxx86file' if platform_key == 'linuxx64file' else 'linuxx64file'
                    if alt_key in item:
                        print(f"[DEBUG] 尝试使用替代架构: {alt_key}")
                        self._process_files(item[alt_key], item)

    def run(self):
        print("[DEBUG] run()方法开始执行")
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
            selected_components = [
                component
                for component, selected in self.components.items()
                if selected
            ]
            total_components = len(selected_components)
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
                self._process_component(component)

                completed_progress = 5 + int(index * 90 / total_components)
                self.progress_updated.emit(
                    completed_progress, f"组件 {component} 安装完成"
                )

            self.success = True
            print("[DEBUG] 所有组件安装成功")
            self.progress_updated.emit(100, "安装完成！")
            
        except Exception as e:
            print(f"[ERROR] 安装过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
            self.progress_updated.emit(0, f"安装失败: {str(e)}")
        finally:
            print(f"[DEBUG] run()方法结束，success={self.success}")
            self.finished.emit(self.success)

    def run_extract(self, archive_name, archive_type, in_path):
        print(f"[DEBUG] run_extract开始: archive_name={archive_name}, archive_type={archive_type}, in_path={in_path}")
        
        # 构建完整路径
        temp = archive_name.split("\\")
        archive_name = os.getcwd()
        archive_name = os.path.join(archive_name, *temp)  # 更简洁
        print(f"[DEBUG] 构建完整压缩包路径: {archive_name}")
        print(f"[DEBUG] 检查压缩包是否存在: {os.path.exists(archive_name)}")
        print(f"[DEBUG] 目标目录是否存在: {os.path.exists(in_path)}")
        
        # 确保目标目录存在
        if not os.path.exists(in_path):
            print(f"[DEBUG] 目标目录不存在，创建: {in_path}")
            os.makedirs(in_path, exist_ok=True)
        
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
            import traceback
            traceback.print_exc()
            raise e

# 基础页面模板
class BasePage(QWidget):
    def __init__(self, parent, has_left_area=False, has_banner=True):
        super().__init__(parent)
        self.parent = parent

        # 设置固定大小
        window_size = QSize()
        window_size.setWidth(WINDOW_SIZE[0])
        window_size.setHeight(WINDOW_SIZE[1])
        self.setFixedSize(window_size)

        try:
            open(get_installer_metadata()["left_pic"]).close()
        except:
            has_left_area = False

        try:
            open(get_installer_metadata()["header_pic"]).close()
        except:
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
            self.left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 加载卡通图片
            self.character_label = QLabel()
            pixmap = QPixmap(get_installer_metadata()["left_pic"])
            if not pixmap.isNull():
                self.character_label.setPixmap(pixmap.scaled(170, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.character_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
                    pixmap.scaled(150, 57, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.header.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # 添加标题
        self.title_label = QLabel()
        title_font = QFont("Microsoft YaHei UI", 12, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 副标题
        self.subtitle_label = QLabel()
        subtitle_font = QFont("Microsoft YaHei UI", 9)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        except:
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
            if IS_RELEASE:
                self.parent.go_to_page("components")
            else:
                self.parent.go_to_page("password")

    def on_cancel(self):
        self.parent.cancel_installation()


# 密码页面
class PasswordPage(BasePage):
    def setup_ui(self):
        self.title_label.setText(PROGRAM_NAME)
        self.subtitle_label.setText("程序需要一个正确的安装密码才能继续")

        # 添加密码输入区域
        password_group = QGroupBox("密码输入框")
        password_layout = QVBoxLayout(password_group)

        if "qq_group" in get_installer_metadata():
            # 添加提示文本
            tip_label = QLabel("请加群 "+get_installer_metadata()["qq_group"]+" 获取密码！")
            tip_label.setStyleSheet("font-size: 9pt; color: #4BA348; font-weight: bold;")

        # 密码输入框
        password_form = QHBoxLayout()
        password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("输入安装密码")

        password_form.addWidget(password_label)
        password_form.addWidget(self.password_input)

        password_layout.addWidget(tip_label)
        password_layout.addLayout(password_form)

        self.content_layout.addWidget(password_group)

        # 添加按钮
        back_btn = self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("license"))
        self.next_button = self.add_button("下一步(N)", self.on_next, "primary")
        self.add_button("取消(C)", self.on_cancel)

        # 连接回车键
        self.password_input.returnPressed.connect(self.on_next)

    def on_next(self):
        if self.password_input.text() == PASSWORD:
            self.parent.go_to_page("components")
        else:
            QMessageBox.warning(self, "密码错误", "请输入正确的安装密码！")

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
        self.components_list.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        self.components_list.setHeaderHidden(True)
        self.components_list.setColumnCount(1)
        self.components_list.setMouseTracking(True)  # 启用鼠标跟踪
        self.components_list.itemEntered.connect(self.on_item_hovered)
        self.components_list.itemClicked.connect(self.on_item_clicked)
        self.components_list.itemChanged.connect(self.on_item_changed)

        metadata = get_metadata()
        for item in metadata["items"]:
            file_not_found = False
            if item["after"] is not None:
                main_item = QTreeWidgetItem()
            else:
                main_item = QTreeWidgetItem(self.components_list)
            main_item.setFlags(main_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if item["files"] is not None:
                for file in item["files"]:
                    path = file.split("\\")
                    r_path = os.getcwd()
                    for p in path:
                        r_path = os.path.join(r_path, p)
                    if not os.path.exists(r_path):
                        file_not_found = True
                        break
            if "x86file" in item:
                for file in item["x86file"]:
                    if not os.path.exists(file):
                        file_not_found = True
                        break
            if "x64file" in item:
                for file in item["x64file"]:
                    if not os.path.exists(file):
                        file_not_found = True
                        break

            if item["required"]:
                if file_not_found:
                    main_item.setText(0, item["name"]+" (未找到对应文件)")
                else:
                    main_item.setText(0, item["name"] + " (必选)")
                main_item.setFlags(main_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                if file_not_found:
                    main_item.setText(0, item["name"] + " (未找到对应文件)")
                    main_item.setFlags(main_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                else:
                    main_item.setText(0, item["name"])
            if "disabled" in item:
                if item["disabled"]:
                    main_item.setFlags(main_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            if item["checked"]:
                if "part_checked" in item:
                    if item["part_checked"]:
                        main_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
                    else:
                        main_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    main_item.setCheckState(0, Qt.CheckState.Checked)
            else: main_item.setCheckState(0, Qt.CheckState.Unchecked)
            main_item.setData(0, Qt.ItemDataRole.UserRole, item["id"])
            if item["after"] is not None:
                for item2 in metadata["items"]:
                    if item2["id"] == item["after"]:
                        self.components_list.findItems(item2["name"], Qt.MatchFlag.MatchContains, 0)[0].addChild(main_item)
                        break

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
        if IS_RELEASE:
            back_btn = self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("license"))
        else:
            back_btn = self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("password"))
        self.next_button = self.add_button("下一步(N)", self.on_next, "primary")
        self.add_button("取消(C)", self.on_cancel)
        self.on_select_change_size.connect(self.on_select_change_size_method)
        self.on_select_change_size.emit(self.get_selected_components_sizes())

    def on_select_change_size_method(self, size:int):
        text = "所需空间："
        KB = 1000  # Use 1024 for binary sizes
        MB = 1000 * 1000
        GB = 1000 * 1000 * 1000
        TB = 1000 * 1000 * 1000 * 1000

        if size < KB:
            text += f"{size} B"
        elif size < MB:
            text += f"{size / KB:.2f} KB"
        elif size < GB:
            text += f"{size / MB:.2f} MB"
        elif size < TB:
            text += f"{size / GB:.2f} GB"
        else:
            text += f"{size / TB:.2f} TB"
		
        self.need_space = size
		
        self.space_label.setText(text)

    def on_next(self):
        # 保存选择的组件
        self.parent.selected_components = {}
        for i in range(self.components_list.topLevelItemCount()):
            item = self.components_list.topLevelItem(i)
            key = item.data(0, Qt.ItemDataRole.UserRole)
            state = item.checkState(0) == Qt.CheckState.Checked

            # 对于父项目，只保存其自身状态
            self.parent.selected_components[key] = state

            # 检查子项目
            for j in range(item.childCount()):
                child = item.child(j)
                child_key = child.data(0, Qt.ItemDataRole.UserRole)
                child_state = child.checkState(0) == Qt.CheckState.Checked
                self.parent.selected_components[child_key] = child_state

        self.parent.need_space = self.need_space
        self.parent.go_to_page("directory")

    def on_cancel(self):
        self.parent.cancel_installation()

    def on_item_hovered(self, item):
        component_key = item.data(0, Qt.ItemDataRole.UserRole)
        metadata = get_metadata()
        description = ""

        for item in metadata["items"]:
            if item["id"] == component_key:
                description = item["desc"]
                break

        if description == "": description = "未找到描述"

        # 更新描述文本
        self.description_text.setHtml(description)

    def on_item_clicked(self, item, column):
        # 如果点击的是父项目，更新子项目的选择状态
        if item.childCount() > 0:
            # 暂时断开信号避免递归调用
            self.components_list.itemChanged.disconnect(self.on_item_changed)

            # 设置所有子项目的状态与父项目一致
            for i in range(item.childCount()):
                child = item.child(i)
                if child.flags() & Qt.ItemFlag.ItemIsEnabled:
                    child.setCheckState(0, item.checkState(0))

            # 重新连接信号
            self.components_list.itemChanged.connect(self.on_item_changed)
        self.on_select_change_size.emit(self.get_selected_components_sizes())

    def get_selected_components_sizes(self):
        size = 0
        for item in get_metadata()["items"]:
            for component in self.find_items_recursive(self.components_list, item["name"]):
                if component.checkState(0) == Qt.CheckState.Checked:
                    for item in get_metadata()["items"]:
                        if item["id"] == component.data(0, Qt.ItemDataRole.UserRole):
                            if item["files"] is not None:
                                for file in item["files"]:
                                    file_type = InstallThread._get_file_type(file)
                                    file = file.replace("/", "\\")
                                    size += self.get_archive_size(file, file_type)
                            if "x64file" in item or "x86file" in item:
                                if platform.machine() == "AMD64":
                                    if "x64file" in item:
                                        for file in item["x64file"]:
                                            file_type = InstallThread._get_file_type(file)
                                            file = file.replace("/", "\\")
                                            size += self.get_archive_size(file, file_type)
                                elif platform.machine() == "x86":
                                    if "x86file" in item:
                                        for file in item["x86file"]:
                                            file_type = InstallThread._get_file_type(file)
                                            file = file.replace("/", "\\")
                                            size += self.get_archive_size(file, file_type)
        return size

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
        except (OSError, EOFError, ValueError, zipfile.BadZipFile, tarfile.TarError) as e:
            print(f"无法读取压缩包大小 {file}: {e}")
            return 0

    def find_component_by_id(self, component_id):
        # 递归搜索QTreeWidget中匹配ID的项目
        def search(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == component_id:
                return item
            for i in range(item.childCount()):
                result = search(item.child(i))
                if result:
                    return result
            return None

        for i in range(self.components_list.topLevelItemCount()):
            result = search(self.components_list.topLevelItem(i))
            if result:
                return result
        return None

    @staticmethod
    def find_items_recursive(tree, text, column=0, match_flag=Qt.MatchFlag.MatchContains):
        def search(items, results):
            for item in items:
                item_text = item.text(column)
                # Check for a match based on the specified flag
                if (
                        (match_flag == Qt.MatchFlag.MatchContains and text in item_text) or
                        (match_flag == Qt.MatchFlag.MatchExactly and item_text == text)
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
        component_key = item.data(0, Qt.ItemDataRole.UserRole)

        # 仅当项目被选中时处理依赖
        if item.checkState(0) == Qt.CheckState.Checked:
            for items in metadata["items"]:
                if items["id"] == component_key:
                    # 获取组件的依赖项列表（假设component_key中有dependencies字段）
                    dependencies = items.get('dependencies', [])
                    for dependency_id in dependencies:
                        # 在当前树中查找依赖项（需要实现find_component_by_id方法）
                        dep_item = self.find_component_by_id(dependency_id)
                        if dep_item and dep_item.checkState(0) != Qt.CheckState.Checked:
                            dep_item.setCheckState(0, Qt.CheckState.Checked)
                    break

        # 当项目状态改变时调用
        if item.parent() is not None:
            # 如果这是子项目，更新父项目的状态
            parent = item.parent()

            # 检查所有子项目的状态
            all_checked = True
            any_checked = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.checkState(0) == Qt.CheckState.Checked:
                    any_checked = True
                else:
                    all_checked = False

            # 暂时断开信号避免递归调用
            self.components_list.itemChanged.disconnect(self.on_item_changed)

            # 设置父项目的状态
            if all_checked:
                parent.setCheckState(0, Qt.CheckState.Checked)
            elif any_checked:
                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                parent.setCheckState(0, Qt.CheckState.Unchecked)

            # 重新连接信号
            self.components_list.itemChanged.connect(self.on_item_changed)

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

        
        if platform.system().lower() == "windows":
            if "default_path" in get_metadata()["items"][MAIN_ITEM]:
                self.default_path = get_metadata()["items"][MAIN_ITEM]["default_path"]
            else:
                self.default_path = ""
        elif platform.system().lower() == "linux":
            if "default_path_linux" in get_metadata()["items"][MAIN_ITEM]:
                self.default_path = get_metadata()["items"][MAIN_ITEM]["default_path_linux"]
            else:
                self.default_path = ""
        elif platform.system().lower() == "darwin":
            if "default_path_macos" in get_metadata()["items"][MAIN_ITEM]:
                self.default_path = get_metadata()["items"][MAIN_ITEM]["default_path_macos"]
            else:
                self.default_path = ""
        else:
            print("Unsupported Operating System found: "+ platform.system().lower())
            self.default_path = ""

        # 路径选择框
        path_form = QHBoxLayout()
        self.path_input = QLineEdit(self.default_path)
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
        back_btn = self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("components"))
        self.install_button = self.add_button("安装(I)", self.on_install, "primary")
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
        path = self.detect_steam_path()
        if path != None:
            self.path_input.setText(path)
            self.update_disk_space()

    def detect_steam_path(self):
        if not "game_name" in get_installer_metadata() or len(get_installer_metadata()["game_name"]) <= 0:
            print("game name not contains in installer metadata, returning default path")
            return self.default_path
        if self.get_steam_path() == None:
            print("steam not installed, return default path")
            return self.default_path
        library_folders = os.path.join(self.get_steam_path(), "steamapps", "libraryfolders.vdf")
        print("library folders file path: "+library_folders)
        if os.path.exists(library_folders):
            import vdf
            with open(library_folders, "r", encoding="utf-8", errors="ignore") as f:
                libraries = vdf.load(f)
            if "game_id" in get_installer_metadata():
                game_id = get_installer_metadata()["game_id"]
                has_game_id = True
            else:
                has_game_id = False
            if "libraryfolders" in libraries:
                for key, value in libraries["libraryfolders"].items():
                    if key.isdigit():  # 只处理数字键（库条目）
                        if has_game_id:
                            if "apps" in value and "path" in value:
                                apps = value.get("apps", {})
                                if str(game_id) in apps:
                                    if os.path.exists(os.path.join(value.get("path"), "steamapps", "common", get_installer_metadata()["game_name"])):
                                        print("Find game folder at: "+os.path.join(value.get("path"), "steamapps", "common", get_installer_metadata()["game_name"]))
                                        return os.path.join(value.get("path"), "steamapps", "common", get_installer_metadata()["game_name"])
                                    else:
                                        print("game folder not at right position, returning default path")
                                        return self.default_path
                            elif "path" in value:
                                if os.path.exists(os.path.join(value.get("path"), "steamapps", "common", get_installer_metadata()["game_name"])):
                                    print("Find game folder at: " + os.path.join(value.get("path"), "steamapps", "common", get_installer_metadata()["game_name"]))
                                    return os.path.join(value.get("path"), "steamapps", "common", get_installer_metadata()["game_name"])
                                else:
                                    continue
                            else:
                                continue
            print("Failed to find game folder, returning default path")
            return self.default_path
        else:
            print("library folders file not exists, returning default path")
            return self.default_path

    def get_steam_path(self):
        arch = platform.machine().lower()
        os_name = platform.system().lower()
        if os_name == "windows":
            import winreg
            if arch == "amd64" or arch == "x86_64":
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\WOW6432Node\Valve\Steam"
                    )
                    path, _ = winreg.QueryValueEx(key, "InstallPath")
                    winreg.CloseKey(key)
                    return path
                except Exception as e:
                    print(f"读取注册表时出错: {e}")
                    return None
            elif arch == "i386" or arch == "x86":
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Valve\Steam"
                    )
                    path, _ = winreg.QueryValueEx(key, "InstallPath")
                    winreg.CloseKey(key)
                    return path
                except Exception as e:
                    print(f"读取注册表时出错: {e}")
                    return None
            else:
                raise NotImplementedError("Not support arm system for now.")
        elif platform.system().lower() == "linux":
            possible_paths = [
                os.path.expanduser("~/.steam/root"), # 最佳：一个指向真实安装目录的符号链接
                os.path.expanduser("~/.local/share/Steam"), # 官方 .deb 包及多数情况下的默认路径
                os.path.expanduser("~/.steam/debian-installation") # Debian 系发行版的特定路径
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    # 如果找到的路径是一个符号链接，我们可以选择跟随它找到真实目录
                    if os.path.islink(path):
                        real_path = os.path.realpath(path)
                        print(f"找到 Steam 安装目录 (通过符号链接): {real_path}")
                        return real_path
                    else:
                        print(f"找到 Steam 安装目录: {path}")
                        return path
            print("Steam文件夹不存在!")
            return None
        elif platform.system().lower() == "darwin":
            possible_paths = [
                os.path.expanduser("~/Library/Application Support/Steam"),
                "/Applications/Steam.app"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    print(f"找到 Steam 目录: {path}")
                    return path
            
            print("未找到 Steam 安装目录!")
            return None
        else:
            raise NotImplementedError("Not support other operating system for now.")

    def page_shown(self, name:str):
        if name == "directory":
            text = "所需空间："
            KB = 1000  # Use 1024 for binary sizes
            MB = 1000 * 1000
            GB = 1000 * 1000 * 1000
            TB = 1000 * 1000 * 1000 * 1000
        
            size = self.parent.need_space
        
            if size < KB:
                text += f"{size} B"
            elif size < MB:
                text += f"{size / KB:.2f} KB"
            elif size < GB:
                text += f"{size / MB:.2f} MB"
            elif size < TB:
                text += f"{size / GB:.2f} GB"
            else:
                text += f"{size / TB:.2f} TB"
            self.required_label.setText(text)

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
        if path and os.path.exists(path):
            try:
                if platform.system().lower() == "windows":
                    drive = os.path.splitdrive(path)[0]
                elif platform.system().lower() == "linux":
                    drive = self._get_mount_point(path)
                elif platform.system().lower() == "darwin":
                    drive = self._get_mount_point(path)
                else:
                    return
                usage = shutil.disk_usage(drive)
                free_space = usage.free / (1024 * 1024)  # MB
                if free_space >= 1024:
                    free_space = free_space / 1024  # GB
                    self.available_label.setText(f"可用空间: {free_space:.1f} GB")
                else:
                    self.available_label.setText(f"可用空间: {free_space:.1f} MB")
                self.available_label.setStyleSheet(
                    "color: green; font-size: 9pt; font-weight: bold; margin: 5px;"
                    if free_space > 15.6
                    else "color: red; font-size: 9pt; font-weight: bold; margin: 5px;"
                )
            except:
                self.available_label.setText("可用空间: 未知")
                self.available_label.setStyleSheet("color: palette(mid); font-size: 9pt;")

    def on_install(self):
        path = self.path_input.text()
        if not path:
            QMessageBox.warning(self, "路径错误", "请选择安装目录！")
            return

        if any(ord(char) > 127 for char in path):
            QMessageBox.warning(self, "路径错误", "安装路径不能包含中文字符！")
            return

        self.parent.install_path = path
        self.parent.go_to_page("install")

    def on_cancel(self):
        self.parent.cancel_installation()


# 安装过程页面
class InstallPage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(*WINDOW_SIZE)

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
            self.result_label.setText(get_installer_metadata()["short_name"]+" 已经成功安装到本机。")
            self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #4BA348;")
        else:
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
        self.setFixedSize(*WINDOW_SIZE)
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "pack", "icon.ico")))

        self.theme_settings = QSettings("Baymaxawa", "UniversalInstaller")
        saved_theme = self.theme_settings.value("appearance/theme", "system")
        self.theme_mode = saved_theme if saved_theme in THEME_MODES else "system"
        self.setup_theme_menu()
        self.apply_theme_mode()

        style_hints = QApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self.on_system_theme_changed)

        metadata = get_metadata()
        if metadata != []:
            self.default_path = metadata["items"][0]["default_path"]

        if "need_admin" in get_installer_metadata():
            if get_installer_metadata()["need_admin"]:
                # 检查管理员权限
                if not is_admin():
                   ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
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
        if IS_RELEASE:
            self.pages = {
                "welcome": WelcomePage(self, True, False, default_path=self.default_path),
                "license": LicensePage(self),
                "components": ComponentsPage(self),
                "directory": DirectoryPage(self),
                "install": InstallPage(self),
                "finish": FinishPage(self)
            }
        else:
            self.pages = {
                "welcome": WelcomePage(self, True, False, default_path=self.default_path),
                "license": LicensePage(self),
                "password": PasswordPage(self),
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

    def setup_theme_menu(self):
        """Create an exclusive System/Light/Dark appearance menu."""
        theme_menu = self.menuBar().addMenu("外观(&V)")
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        self.theme_actions = {}

        for mode, label in THEME_MODES.items():
            action = QAction(label, self, checkable=True)
            action.setData(mode)
            action.setChecked(mode == self.theme_mode)
            action.triggered.connect(
                lambda checked=False, selected_mode=mode: self.set_theme_mode(
                    selected_mode
                )
            )
            self.theme_action_group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[mode] = action

    def set_theme_mode(self, mode):
        if mode not in THEME_MODES:
            raise ValueError(f"未知主题模式: {mode}")
        self.theme_mode = mode
        self.theme_settings.setValue("appearance/theme", mode)
        self.theme_actions[mode].setChecked(True)
        self.apply_theme_mode()

    def apply_theme_mode(self):
        active_theme = get_system_theme() if self.theme_mode == "system" else self.theme_mode
        apply_application_theme(active_theme)

    def on_system_theme_changed(self, _color_scheme):
        if self.theme_mode == "system":
            self.apply_theme_mode()

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


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用程序字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
