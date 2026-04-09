import json
import os
import sys
import shutil
import winreg
import ctypes

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QTextEdit, QGroupBox, QFrame
)
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt, QThread, Signal

WINDOW_SIZE = (640, 480)
MANIFEST_NAME = "install_manifest.json"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def load_manifest():
    """从安装目录加载安装清单"""
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), MANIFEST_NAME)
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class UninstallThread(QThread):
    progress_updated = Signal(int, str)
    finished = Signal(bool)

    def __init__(self, install_path, components_to_remove, manifest, remove_registry):
        super().__init__()
        self.install_path = install_path
        self.components_to_remove = components_to_remove
        self.manifest = manifest
        self.remove_registry = remove_registry

    def run(self):
        try:
            total = len(self.components_to_remove)
            if total == 0:
                self.progress_updated.emit(100, "没有选择任何组件。")
                self.finished.emit(True)
                return

            step = 90 / max(total, 1)
            current_progress = 5
            self.progress_updated.emit(5, "正在准备卸载...")

            installed_components = self.manifest.get("installed_components", {})

            for comp_id in self.components_to_remove:
                comp_info = installed_components.get(comp_id, {})
                comp_name = comp_info.get("name", comp_id)
                current_progress += step
                self.progress_updated.emit(int(current_progress), f"正在卸载组件: {comp_name}...")

                # 删除该组件安装的文件和目录
                installed_paths = comp_info.get("installed_paths", [])
                for path in installed_paths:
                    full_path = path
                    if not os.path.isabs(full_path):
                        full_path = os.path.join(self.install_path, path)
                    try:
                        if os.path.isfile(full_path):
                            os.remove(full_path)
                            self.progress_updated.emit(0, f"  已删除文件: {full_path}")
                        elif os.path.isdir(full_path):
                            shutil.rmtree(full_path)
                            self.progress_updated.emit(0, f"  已删除目录: {full_path}")
                    except Exception as e:
                        self.progress_updated.emit(0, f"  删除失败: {full_path} ({e})")

            # 如果需要，删除注册表项
            if self.remove_registry:
                self.progress_updated.emit(95, "正在清理注册表...")
                registry_key = self.manifest.get("registry_key", "")
                uninstall_reg_key = self.manifest.get("uninstall_registry_key", "")
                if registry_key:
                    try:
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry_key)
                        self.progress_updated.emit(0, "  已删除安装注册表项")
                    except FileNotFoundError:
                        pass
                    except Exception as e:
                        self.progress_updated.emit(0, f"  注册表清理失败: {e}")
                if uninstall_reg_key:
                    try:
                        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, uninstall_reg_key)
                        self.progress_updated.emit(0, "  已删除卸载注册表项")
                    except FileNotFoundError:
                        pass
                    except PermissionError:
                        self.progress_updated.emit(0, "  警告: 无法删除卸载注册表项，可能需要管理员权限")
                    except Exception as e:
                        self.progress_updated.emit(0, f"  注册表清理失败: {e}")

            # 更新清单文件 — 移除已卸载的组件
            for comp_id in self.components_to_remove:
                installed_components.pop(comp_id, None)
            self.manifest["installed_components"] = installed_components

            manifest_path = os.path.join(
                os.path.dirname(os.path.abspath(sys.argv[0])), MANIFEST_NAME
            )
            if len(installed_components) == 0:
                # 所有组件已卸载，删除清单和卸载程序自身
                try:
                    os.remove(manifest_path)
                except Exception:
                    pass
                self.progress_updated.emit(0, "所有组件已卸载，清单已清理。")
            else:
                try:
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(self.manifest, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            self.progress_updated.emit(100, "卸载完成！")
            self.finished.emit(True)
        except Exception as e:
            self.progress_updated.emit(0, f"卸载失败: {str(e)}")
            self.finished.emit(False)


class UninstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.manifest = load_manifest()
        if self.manifest is None:
            QMessageBox.critical(
                self, "错误",
                f"找不到安装清单文件 ({MANIFEST_NAME})。\n"
                "请确保卸载程序位于安装目录中。"
            )
            sys.exit(1)

        self.program_name = self.manifest.get("program_name", "程序")
        self.install_path = self.manifest.get("install_path", "")
        self.main_item_id = self.manifest.get("main_item_id", "")
        self.items_meta = self.manifest.get("items_metadata", [])

        self.setWindowTitle(f"{self.program_name} - 卸载程序")
        self.setFixedSize(*WINDOW_SIZE)

        icon_path = self.manifest.get("icon", "")
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 主容器
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel(f"{self.program_name} - 卸载程序")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        subtitle = QLabel("请选择要卸载的组件：")
        subtitle.setStyleSheet("font-size: 10pt; color: #666;")
        main_layout.addWidget(subtitle)

        # 组件树
        self.component_tree = QTreeWidget()
        self.component_tree.setHeaderHidden(True)
        self.component_tree.setRootIsDecorated(True)
        main_layout.addWidget(self.component_tree)

        self.populate_tree()

        # 进度区域（初始隐藏）
        self.progress_group = QGroupBox("卸载进度")
        progress_layout = QVBoxLayout(self.progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(120)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_area)
        self.progress_group.setVisible(False)
        main_layout.addWidget(self.progress_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.uninstall_btn = QPushButton("卸载选中组件(U)")
        self.uninstall_btn.setStyleSheet(
            "QPushButton { background-color: #d9534f; color: white; "
            "padding: 8px 20px; border: none; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #c9302c; }"
        )
        self.uninstall_btn.clicked.connect(self.on_uninstall)
        btn_layout.addWidget(self.uninstall_btn)

        self.close_btn = QPushButton("关闭(C)")
        self.close_btn.setStyleSheet("padding: 8px 20px;")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)

    def populate_tree(self):
        """根据安装清单构建组件树"""
        installed = self.manifest.get("installed_components", {})
        # 构建 id -> meta 映射
        meta_map = {}
        for item in self.items_meta:
            meta_map[item["id"]] = item

        # 先添加顶级项（after == null），再添加子项
        top_items = {}
        child_items = {}
        for comp_id in installed:
            meta = meta_map.get(comp_id, {})
            after = meta.get("after")
            if after is None:
                top_items[comp_id] = meta
            else:
                child_items.setdefault(after, []).append((comp_id, meta))

        tree_items_map = {}
        for comp_id, meta in top_items.items():
            name = meta.get("name", comp_id)
            tree_item = QTreeWidgetItem(self.component_tree, [name])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, comp_id)
            is_required = meta.get("required", False)
            tree_item.setCheckState(0, Qt.CheckState.Checked)
            tree_items_map[comp_id] = tree_item

        for parent_id, children in child_items.items():
            parent_tree_item = tree_items_map.get(parent_id)
            for comp_id, meta in children:
                name = meta.get("name", comp_id)
                if parent_tree_item:
                    tree_item = QTreeWidgetItem(parent_tree_item, [name])
                else:
                    tree_item = QTreeWidgetItem(self.component_tree, [name])
                tree_item.setData(0, Qt.ItemDataRole.UserRole, comp_id)
                tree_item.setCheckState(0, Qt.CheckState.Checked)
                tree_items_map[comp_id] = tree_item

        self.component_tree.expandAll()

    def get_checked_components(self):
        """获取所有被勾选的组件ID"""
        checked = []

        def collect(item):
            if item.checkState(0) == Qt.CheckState.Checked:
                comp_id = item.data(0, Qt.ItemDataRole.UserRole)
                if comp_id:
                    checked.append(comp_id)
            for i in range(item.childCount()):
                collect(item.child(i))

        for i in range(self.component_tree.topLevelItemCount()):
            collect(self.component_tree.topLevelItem(i))
        return checked

    def on_uninstall(self):
        selected = self.get_checked_components()
        if not selected:
            QMessageBox.information(self, "提示", "请至少选择一个要卸载的组件。")
            return

        # 检查是否包含核心组件
        remove_registry = self.main_item_id in selected
        installed = self.manifest.get("installed_components", {})

        # 组件名称列表
        names = []
        for comp_id in selected:
            comp_info = installed.get(comp_id, {})
            names.append(comp_info.get("name", comp_id))

        msg = "确定要卸载以下组件吗？\n\n" + "\n".join(f"  - {n}" for n in names)
        if remove_registry:
            msg += "\n\n注意：核心组件将被卸载，注册表项也将一并清除。"

        reply = QMessageBox.question(
            self, "确认卸载", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 开始卸载
        self.uninstall_btn.setEnabled(False)
        self.component_tree.setEnabled(False)
        self.progress_group.setVisible(True)
        self.log_area.clear()
        self.log_area.append("开始卸载...")

        self.thread = UninstallThread(
            self.install_path, selected, self.manifest, remove_registry
        )
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.finished.connect(self.uninstall_finished)
        self.thread.start()

    def update_progress(self, value, message):
        if value > 0:
            self.progress_bar.setValue(value)
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def uninstall_finished(self, success):
        if success:
            QMessageBox.information(self, "完成", "选中的组件已成功卸载。")
        else:
            QMessageBox.warning(self, "警告", "卸载过程中出现错误，请检查日志。")
        self.close()


def main():
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    window = UninstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
