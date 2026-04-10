import json
import os
import platform
import sys
import shutil
import time
import winreg
import ctypes
import zipfile
import rarfile
import py7zr
import tarfile

from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QCheckBox, QLineEdit, QFileDialog,
    QProgressBar, QGroupBox, QFrame, QMessageBox, QTreeWidget,
    QTreeWidgetItem
)
from PySide2.QtGui import QPixmap, QIcon, QFont
from PySide2.QtCore import Qt, QThread, Signal, QSize
from qfluentwidgets import setTheme, Theme
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
        with open(METADATA_PATH, "r", encoding='utf-8') as file:
            metadata = json.load(file)
            return metadata
    except Exception as e:
        print(e)
        return {}

# 全局常量
PROGRAM_NAME : str = get_installer_metadata()["program_name"]
VERSION : str = get_installer_metadata()["version"]
IS_RELEASE : bool = get_installer_metadata()["is_release"]
REGISTRY_KEY : str = "Software\\"+get_installer_metadata()["registry_key_name"]
UNINSTALL_REG_KEY : str = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"+get_installer_metadata()["uninstall_registry_key_name"]
WINDOW_SIZE = (640, 480)  # 固定窗口大小
METADATA_PATH : str = get_installer_metadata()["item_metadata"]
MAIN_ITEM : int = get_installer_metadata()["main_item"]

# 检查管理员权限的函数
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
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
        self.installed_paths = {}  # comp_id -> list of installed paths

    def run(self):
        try:
            # 0. 准备工作
            self.progress_updated.emit(5, "正在准备安装环境...")
            if not os.path.exists(self.path):
                os.makedirs(self.path, exist_ok=True)

            time.sleep(2)
            # 2. 安装组件
            step = 85 / max(len(self.components), 1)
            current_progress = 5
            for component in self.components:
                if self.components[component]:
                    current_progress += step
                    self.progress_updated.emit(int(current_progress), "正在安装组件"+component+"...")
                    self.installed_paths[component] = []
                    for item in get_metadata()["items"]:
                        if item["id"] == component:
                            if item["files"] is not None:
                                for file in item["files"]:
                                    in_path : str = ""
                                    file_type = ""
                                    result = file.split(".")
                                    if file in item["actions"]:
                                        in_path = item["actions"][file]
                                        in_path = in_path.replace("{install_path}", self.path)
                                        in_path = in_path.replace("/", "\\")
                                    else:
                                        continue
                                    ext = result[-1] if len(result) > 1 else ""
                                    if ext == "zip":
                                        file_type = "zip"
                                    elif ext == "rar":
                                        file_type = "rar"
                                    elif ext == "7z":
                                        file_type = "7z"
                                    elif ext == "tar":
                                        file_type = "tar"
                                    elif ext == "txt":
                                        shutil.copy(file, in_path)
                                        self.installed_paths[component].append(in_path)
                                        continue
                                    else:
                                        continue
                                    file = file.replace("/", "\\")
                                    extracted = self.run_extract(file, file_type, in_path)
                                    self.installed_paths[component].extend(extracted)
                            if "x64file" in item or "x86file" in item:
                                if platform.machine() == "AMD64":
                                    if "x64file" in item:
                                        for file in item["x64file"]:
                                            in_path: str = ""
                                            file_type = ""
                                            result = file.split(".")
                                            if file in item["actions"]:
                                                in_path = item["actions"][file]
                                                in_path = in_path.replace("{install_path}", self.path)
                                                in_path = in_path.replace("/", "\\")
                                            else:
                                                continue
                                            ext = result[-1] if len(result) > 1 else ""
                                            if ext == "zip":
                                                file_type = "zip"
                                            elif ext == "rar":
                                                file_type = "rar"
                                            elif ext == "7z":
                                                file_type = "7z"
                                            elif ext == "tar":
                                                file_type = "tar"
                                            else:
                                                continue
                                            file = file.replace("/", "\\")
                                            extracted = self.run_extract(file, file_type, in_path)
                                            self.installed_paths[component].extend(extracted)
                                elif platform.machine() == "x86":
                                    if "x86file" in item:
                                        for file in item["x86file"]:
                                            in_path: str = ""
                                            file_type = ""
                                            result = file.split(".")
                                            if file in item["actions"]:
                                                in_path = item["actions"][file]
                                                in_path = in_path.replace("{install_path}", self.path)
                                                in_path = in_path.replace("/", "\\")
                                            else:
                                                continue
                                            ext = result[-1] if len(result) > 1 else ""
                                            if ext == "zip":
                                                file_type = "zip"
                                            elif ext == "rar":
                                                file_type = "rar"
                                            elif ext == "7z":
                                                file_type = "7z"
                                            elif ext == "tar":
                                                file_type = "tar"
                                            else:
                                                continue
                                            file = file.replace("/", "\\")
                                            extracted = self.run_extract(file, file_type, in_path)
                                            self.installed_paths[component].extend(extracted)
            time.sleep(2)

            # 3. 保存安装清单和卸载程序
            self.progress_updated.emit(92, "正在生成卸载程序...")
            self.save_install_manifest()
            self.copy_uninstaller()

            ## 4. 注册表操作
            #self.progress_updated.emit(95, "正在更新系统设置...")
            #self.create_registry_entries()

            self.success = True
            self.progress_updated.emit(100, "安装完成！")
        except Exception as e:
            print(e)
            self.progress_updated.emit(0, f"安装失败: {str(e)}")
        finally:
            self.finished.emit(self.success)

    def run_extract(self, archive_name, archive_type, in_path):
        self.progress_updated.emit(0, "正在解压文件" + archive_name + "...")
        extracted_paths = []
        try:
            if archive_type == "zip":
                with zipfile.ZipFile(archive_name, "r") as archive:
                    extracted_paths = [os.path.join(in_path, n) for n in archive.namelist()]
                    archive.extractall(in_path)
            elif archive_type == "rar":
                with rarfile.RarFile(archive_name, "r") as archive:
                    extracted_paths = [os.path.join(in_path, n) for n in archive.namelist()]
                    archive.extractall(in_path)
            elif archive_type == "7z":
                with py7zr.SevenZipFile(archive_name, "r") as archive:
                    extracted_paths = [os.path.join(in_path, n) for n in archive.getnames()]
                    archive.extractall(in_path)
            elif archive_type == "tar":
                with tarfile.TarFile(archive_name, "r") as archive:
                    extracted_paths = [os.path.join(in_path, n) for n in archive.getnames()]
                    archive.extractall(in_path)
            else:
                return []
            self.progress_updated.emit(0, f"解压成功: {archive_name}")
        except Exception as e:
            print(e)
            raise e
        return extracted_paths

    def save_install_manifest(self):
        """保存安装清单到安装目录，供卸载程序使用"""
        items_meta = get_metadata().get("items", [])
        installed_components = {}
        for comp_id, paths in self.installed_paths.items():
            comp_name = comp_id
            for item in items_meta:
                if item["id"] == comp_id:
                    comp_name = item.get("name", comp_id)
                    break
            installed_components[comp_id] = {
                "name": comp_name,
                "installed_paths": paths
            }

        # 找出核心组件 ID
        main_item_id = ""
        if MAIN_ITEM < len(items_meta):
            main_item_id = items_meta[MAIN_ITEM]["id"]

        manifest = {
            "program_name": PROGRAM_NAME,
            "version": VERSION,
            "install_path": self.path,
            "main_item_id": main_item_id,
            "registry_key": REGISTRY_KEY,
            "uninstall_registry_key": UNINSTALL_REG_KEY,
            "items_metadata": items_meta,
            "installed_components": installed_components
        }

        manifest_path = os.path.join(self.path, "install_manifest.json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            self.progress_updated.emit(0, "安装清单已保存")
        except Exception as e:
            self.progress_updated.emit(0, f"保存安装清单失败: {e}")

    def copy_uninstaller(self):
        """将卸载程序复制到安装目录"""
        # 查找卸载程序（与安装程序同目录或打包后的资源目录）
        uninstaller_name = "Uninstall.exe"
        src_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), uninstaller_name),
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "uninstaller.exe"),
        ]
        dest_path = os.path.join(self.path, uninstaller_name)
        for src in src_candidates:
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dest_path)
                    self.progress_updated.emit(0, "卸载程序已复制")
                    return
                except Exception as e:
                    self.progress_updated.emit(0, f"复制卸载程序失败: {e}")
                    return
        self.progress_updated.emit(0, "警告: 未找到卸载程序文件，跳过")

    def create_registry_entries(self):
        # 创建安装信息注册表项
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, self.path)
            winreg.CloseKey(key)
        except:
            pass

        # 创建卸载注册表项
        try:
            uninstall_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_REG_KEY)
            winreg.SetValueEx(uninstall_key, "DisplayName", 0, winreg.REG_SZ, "BB+汉化")
            winreg.SetValueEx(uninstall_key, "UninstallString", 0, winreg.REG_SZ,
                              f'"{os.path.join(self.path, "Uninstall.exe")}"')
            winreg.SetValueEx(uninstall_key, "InstallLocation", 0, winreg.REG_SZ, self.path)
            winreg.SetValueEx(uninstall_key, "DisplayIcon", 0, winreg.REG_SZ, os.path.join(self.path, "icon.ico"))
            winreg.SetValueEx(uninstall_key, "Publisher", 0, winreg.REG_SZ, "MEMZSystem32 & Baymaxawa")
            winreg.SetValueEx(uninstall_key, "Readme", 0, winreg.REG_SZ, os.path.join(self.path, "readme.txt"))
            winreg.SetValueEx(uninstall_key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
            winreg.SetValueEx(uninstall_key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(uninstall_key, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(uninstall_key, "EstimatedSize", 0, winreg.REG_DWORD, 102400)  # 100MB
            winreg.CloseKey(uninstall_key)
        except PermissionError:
            # 处理没有管理员权限的情况
            self.progress_updated.emit(0, "警告: 无法写入注册表，可能缺少管理员权限")
        except Exception as e:
            self.progress_updated.emit(0, f"注册表错误: {str(e)}")


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

        if not os.path.exists(get_installer_metadata().get("left_pic", "")):
            has_left_area = False

        if not os.path.exists(get_installer_metadata().get("header_pic", "")):
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
        self.footer_label.setStyleSheet("color: #666666; font-size: 8pt;")
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
        button.setMinimumSize(100, 32)

        if style == "primary":
            button.setStyleSheet("background-color: #0078D4; color: white; border: none; border-radius: 4px; padding: 6px 20px;")

        button.clicked.connect(callback)
        self.button_layout.addWidget(button)
        return button


# 欢迎页面
class WelcomePage(BasePage):
    def __init__(self, *args, default_path: str, **kwargs):
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
        except:
            self.license_text.setText("许可协议文件未找到。\n一般意味着此工具为 All Rights Reserved 协议。")

        # 添加提示文本
        tip_label = QLabel("要阅读协议的其余部分，请使用滚动条浏览。")
        tip_label.setStyleSheet("font-size: 9pt; color: #666666;")

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
            self.parent.go_to_page("components")

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
        self.components_list.setSelectionMode(QTreeWidget.MultiSelection)
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
            main_item.setFlags(main_item.flags() | Qt.ItemIsUserCheckable)
            if item["files"] is not None:
                for file in item["files"]:
                    path = file.replace("/", "\\")
                    path = ".\\" + path
                    if not os.path.exists(file):
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
                main_item.setFlags(main_item.flags() & ~Qt.ItemIsEnabled)
            else:
                if file_not_found:
                    main_item.setText(0, item["name"] + " (未找到对应文件)")
                    main_item.setFlags(main_item.flags() & ~Qt.ItemIsEnabled)
                else:
                    main_item.setText(0, item["name"])
            if "disabled" in item:
                if item["disabled"]:
                    main_item.setFlags(main_item.flags() & ~Qt.ItemIsEnabled)
            if item["checked"]:
                if "part_checked" in item:
                    if item["part_checked"]:
                        main_item.setCheckState(0, Qt.PartiallyChecked)
                    else:
                        main_item.setCheckState(0, Qt.Checked)
                else:
                    main_item.setCheckState(0, Qt.Checked)
            else: main_item.setCheckState(0, Qt.Unchecked)
            main_item.setData(0, Qt.UserRole, item["id"])
            if item["after"] is not None:
                for item2 in metadata["items"]:
                    if item2["id"] == item["after"]:
                        self.components_list.findItems(item2["name"], Qt.MatchContains, 0)[0].addChild(main_item)
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
        back_btn = self.add_button("< 上一步(P)", lambda: self.parent.go_to_page("license"))
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
            key = item.data(0, Qt.UserRole)
            state = item.checkState(0) == Qt.Checked

            # 对于父项目，只保存其自身状态
            self.parent.selected_components[key] = state

            # 检查子项目
            for j in range(item.childCount()):
                child = item.child(j)
                child_key = child.data(0, Qt.UserRole)
                child_state = child.checkState(0) == Qt.Checked
                self.parent.selected_components[child_key] = child_state

        self.parent.need_space = self.need_space
        self.parent.go_to_page("directory")

    def on_cancel(self):
        self.parent.cancel_installation()

    def on_item_hovered(self, item):
        component_key = item.data(0, Qt.UserRole)
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
                if child.flags() & Qt.ItemIsEnabled:
                    child.setCheckState(0, item.checkState(0))

            # 重新连接信号
            self.components_list.itemChanged.connect(self.on_item_changed)
        self.on_select_change_size.emit(self.get_selected_components_sizes())

    def get_selected_components_sizes(self):
        size = 0
        for meta_item in get_metadata()["items"]:
            for component in self.find_items_recursive(self.components_list, meta_item["name"]):
                if component.checkState(0) == Qt.Checked:
                    for inner_item in get_metadata()["items"]:
                        if inner_item["id"] == component.data(0, Qt.UserRole):
                            if inner_item["files"] is not None:
                                for file in inner_item["files"]:
                                    file_type = ""
                                    result = file.split(".")
                                    ext = result[-1] if len(result) > 1 else ""
                                    if ext == "zip":
                                        file_type = "zip"
                                    elif ext == "rar":
                                        file_type = "rar"
                                    elif ext == "7z":
                                        file_type = "7z"
                                    elif ext == "tar":
                                        file_type = "tar"
                                    else:
                                        continue
                                    file = file.replace("/", "\\")
                                    size += self.get_archive_size(file, file_type)
                            if "x64file" in inner_item or "x86file" in inner_item:
                                if platform.machine() == "AMD64":
                                    if "x64file" in inner_item:
                                        for file in inner_item["x64file"]:
                                            file_type = ""
                                            result = file.split(".")
                                            ext = result[-1] if len(result) > 1 else ""
                                            if ext == "zip":
                                                file_type = "zip"
                                            elif ext == "rar":
                                                file_type = "rar"
                                            elif ext == "7z":
                                                file_type = "7z"
                                            elif ext == "tar":
                                                file_type = "tar"
                                            else:
                                                continue
                                            file = file.replace("/", "\\")
                                            size += self.get_archive_size(file, file_type)
                                elif platform.machine() == "x86":
                                    if "x86file" in inner_item:
                                        for file in inner_item["x86file"]:
                                            file_type = ""
                                            result = file.split(".")
                                            ext = result[-1] if len(result) > 1 else ""
                                            if ext == "zip":
                                                file_type = "zip"
                                            elif ext == "rar":
                                                file_type = "rar"
                                            elif ext == "7z":
                                                file_type = "7z"
                                            elif ext == "tar":
                                                file_type = "tar"
                                            else:
                                                continue
                                            file = file.replace("/", "\\")
                                            size += self.get_archive_size(file, file_type)
        return size

    @staticmethod
    def get_archive_size(file, file_type) -> int:
        if file_type == "zip":
            import zipfile
            try:
                with zipfile.ZipFile(file, 'r') as zip_ref:
                    return sum(info.file_size for info in zip_ref.infolist())
            except Exception as e:
                print(e)
                return 0
        elif file_type == "rar":
            import rarfile
            try:
                with rarfile.RarFile(file, 'r') as rar_ref:
                    return sum(f.file_size for f in rar_ref.infolist())
            except Exception as e:
                print(e)
                return 0
        elif file_type == "7z":
            import py7zr
            try:
                with py7zr.SevenZipFile(file, 'r') as sevenzip_ref:
                    return sum(f.file_properties().get("uncompressed") for f in sevenzip_ref.files)
            except Exception as e:
                print(e)
                return 0
        elif file_type == "tar":
            import tarfile
            try:
                with tarfile.open(file, 'r:*') as tar_ref:
                    return sum(m.size for m in tar_ref.getmembers() if m.isfile())
            except Exception as e:
                print(e)
                return 0
        else:
            raise NotImplementedError("Not Implemented Type: " + file_type)

    def find_component_by_id(self, component_id):
        # 递归搜索QTreeWidget中匹配ID的项目
        def search(item):
            if item.data(0, Qt.UserRole) == component_id:
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

    def get_incompatible_ids(self, component_id):
        """获取某个组件的不兼容组件ID列表"""
        for items in get_metadata()["items"]:
            if items["id"] == component_id:
                return items.get('incompatible', [])
        return []

    def is_disabled_by_incompatible(self, component_id):
        """检查某个组件是否因为与其他已选中的组件不兼容而应该被禁用"""
        for items in get_metadata()["items"]:
            incompat_list = items.get('incompatible', [])
            if component_id in incompat_list:
                tree_item = self.find_component_by_id(items["id"])
                if tree_item and tree_item.checkState(0) == Qt.Checked:
                    return True
            if items["id"] == component_id:
                for incompat_id in items.get('incompatible', []):
                    tree_item = self.find_component_by_id(incompat_id)
                    if tree_item and tree_item.checkState(0) == Qt.Checked:
                        return True
        return False

    def get_component_name(self, component_id):
        """根据组件ID获取组件名称"""
        for items in get_metadata()["items"]:
            if items["id"] == component_id:
                return items.get("name", component_id)
        return component_id

    def on_item_changed(self, item, column):
        component_key = item.data(0, Qt.UserRole)

        # 仅当项目被选中时处理依赖
        if item.checkState(0) == Qt.Checked:
            # 依赖处理：保持信号连接，让依赖项递归触发 on_item_changed
            # 这样 A→B→C 的传递依赖能正确处理
            for items in get_metadata()["items"]:
                if items["id"] == component_key:
                    # 获取组件的依赖项列表
                    dependencies = items.get('dependencies', [])
                    for dependency_id in dependencies:
                        dep_item = self.find_component_by_id(dependency_id)
                        if dep_item and dep_item.checkState(0) != Qt.Checked:
                            dep_item.setCheckState(0, Qt.Checked)
                    break

            # 处理不兼容组件 — 断开信号避免复杂的重入行为
            self.components_list.itemChanged.disconnect(self.on_item_changed)
            incompatible_ids = self.get_incompatible_ids(component_key)
            for incompat_id in incompatible_ids:
                incompat_item = self.find_component_by_id(incompat_id)
                if incompat_item is None:
                    continue
                if incompat_item.checkState(0) == Qt.Checked:
                    # 两个不兼容组件都被选中，弹窗让用户选择
                    current_name = self.get_component_name(component_key)
                    other_name = self.get_component_name(incompat_id)
                    # 重新连接信号后再弹窗（弹窗会阻塞事件循环）
                    self.components_list.itemChanged.connect(self.on_item_changed)
                    reply = QMessageBox.question(
                        self, "组件冲突",
                        f"「{current_name}」与「{other_name}」不兼容，不能同时安装。\n\n"
                        f"选择「是」保留「{current_name}」，\n"
                        f"选择「否」保留「{other_name}」。",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    self.components_list.itemChanged.disconnect(self.on_item_changed)
                    if reply == QMessageBox.Yes:
                        # 保留当前组件，取消另一个
                        incompat_item.setCheckState(0, Qt.Unchecked)
                        incompat_item.setFlags(incompat_item.flags() & ~Qt.ItemIsEnabled)
                    else:
                        # 保留另一个，取消当前组件
                        item.setCheckState(0, Qt.Unchecked)
                        item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                        # 当前组件已被取消，跳出循环
                        break
                else:
                    # 不兼容组件未被选中，禁用它
                    incompat_item.setCheckState(0, Qt.Unchecked)
                    incompat_item.setFlags(incompat_item.flags() & ~Qt.ItemIsEnabled)
            self.components_list.itemChanged.connect(self.on_item_changed)

        elif item.checkState(0) == Qt.Unchecked:
            # 取消选中时，重新启用被此组件禁用的不兼容组件
            # 断开信号避免重入
            self.components_list.itemChanged.disconnect(self.on_item_changed)
            incompatible_ids = self.get_incompatible_ids(component_key)
            for incompat_id in incompatible_ids:
                incompat_item = self.find_component_by_id(incompat_id)
                if incompat_item is None:
                    continue
                # 检查该不兼容组件是否还被其他已选中的组件禁用
                if not self.is_disabled_by_incompatible(incompat_id):
                    # 检查组件本身是否在metadata中被标记为disabled
                    meta_disabled = False
                    for meta_item in get_metadata()["items"]:
                        if meta_item["id"] == incompat_id:
                            meta_disabled = meta_item.get("disabled", False)
                            break
                    if not meta_disabled:
                        incompat_item.setFlags(incompat_item.flags() | Qt.ItemIsEnabled)
            self.components_list.itemChanged.connect(self.on_item_changed)

        # 当项目状态改变时调用 — 断开信号避免父↔子无限递归
        if item.parent() is not None:
            # 如果这是子项目，更新父项目的状态
            parent = item.parent()

            self.components_list.itemChanged.disconnect(self.on_item_changed)
            # 检查所有子项目的状态
            all_checked = True
            any_checked = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.checkState(0) == Qt.Checked:
                    any_checked = True
                else:
                    all_checked = False

            # 设置父项目的状态
            if all_checked:
                parent.setCheckState(0, Qt.Checked)
            elif any_checked:
                parent.setCheckState(0, Qt.PartiallyChecked)
            else:
                parent.setCheckState(0, Qt.Unchecked)
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
            tip_label.setStyleSheet("font-size: 10pt; color: #666666;")
            path_layout.addWidget(tip_label)

        self.default_path = get_metadata()["items"][MAIN_ITEM]["default_path"]

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
        self.path_input.setText(self.detect_steam_path())

    def detect_steam_path(self):
        if not "game_name" in get_installer_metadata() or len(get_installer_metadata()["game_name"]) <= 0:
            print("game name not contains in installer metadata, returning default path")
            return self.default_path
        steam_path = self.get_steam_path()
        if steam_path is None:
            print("Steam path not found, returning default path")
            return self.default_path
        library_folders = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
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
        else:
            return None

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

    def update_disk_space(self):
        
        path = self.path_input.text()
        if path and os.path.exists(path):
            drive = os.path.splitdrive(path)[0]
            try:
                usage = shutil.disk_usage(drive)
                free_space = usage.free / (1024 * 1024)  # MB
                self.available_label.setText(f"可用空间: {free_space:.1f} MB")
                if free_space > 15.6:
                    self.available_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin: 5px; color: #107C10;")
                else:
                    self.available_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin: 5px; color: #D13438;")
            except:
                self.available_label.setText("可用空间: 未知")
                self.available_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin: 5px; color: #666666;")

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
        self.log_area.setStyleSheet("font-family: Consolas, monospace;")

        logs_layout.addWidget(self.log_area)
        main_layout.addWidget(logs_group)

        # 按钮区域
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch(1)

        # 显示详情按钮
        self.details_button = QPushButton("隐藏详情(D)")
        self.details_button.clicked.connect(self.toggle_details)
        self.button_layout.addWidget(self.details_button)

        # 添加按钮
        self.next_button = self.add_button("下一步(F)", self.on_next, "primary")
        self.next_button.setEnabled(False)

        main_layout.addLayout(self.button_layout)

        # 底部信息
        footer_label = QLabel(get_installer_metadata()["footer_info"])
        footer_label.setStyleSheet("color: #666666; font-size: 8pt;")
        footer_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(footer_label)

        # 初始化时显示日志区域
        self.log_area_visible = True

    def add_button(self, text, callback, style="default"):
        button = QPushButton(text)
        button.setMinimumSize(100, 32)

        if style == "primary":
            button.setStyleSheet("background-color: #0078D4; color: white; border: none; border-radius: 4px; padding: 6px 20px;")

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
        self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #107C10;")
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
            self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #107C10;")
        else:
            self.result_label.setText("安装失败，请检查错误信息后重试。")
            self.result_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #D13438;")

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
        self.setWindowIcon(QIcon("icon.ico"))

        metadata = get_metadata()
        if metadata != {}:
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

    # 应用 WinUI 3 主题（自动跟随系统深色/浅色模式）
    setTheme(Theme.AUTO)

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
