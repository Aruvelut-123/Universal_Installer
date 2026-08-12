from __future__ import annotations

import argparse
import base64
import errno
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zlib
from datetime import datetime
from pathlib import Path

from responsive_ui import (
    add_wizard_button,
    configure_high_dpi,
    configure_responsive_window,
    responsive_image_label_class,
    responsive_ui_metrics,
)
from runtime_paths import resolve_application_directory
from windows_style import (
    apply_windows_window_effects,
    configure_windows_qt_style,
    windows_app_theme,
    windows_style_profile,
)

INSTALL_DATA_DIRECTORY = ".universal_installer"
INSTALL_MANIFEST_NAME = "install_info.uim"
MANIFEST_MAGIC = b"UIM\x01"
MAX_MANIFEST_SIZE = 16 * 1024 * 1024


def _is_relative_to(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _encode_manifest(data):
    payload = json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return MANIFEST_MAGIC + zlib.compress(payload, level=9)


def _decode_manifest(data):
    if not data.startswith(MANIFEST_MAGIC):
        raise ValueError("安装信息不是受支持的 UIM 格式")
    decompressor = zlib.decompressobj()
    payload = decompressor.decompress(
        data[len(MANIFEST_MAGIC):], MAX_MANIFEST_SIZE + 1
    )
    if len(payload) > MAX_MANIFEST_SIZE or decompressor.unconsumed_tail:
        raise ValueError("安装信息解压后超过大小限制")
    payload += decompressor.flush()
    if len(payload) > MAX_MANIFEST_SIZE or not decompressor.eof:
        raise ValueError("安装信息压缩数据无效")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("安装信息内容无效: {}".format(error)) from error


def _atomic_write_manifest(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as file:
        file.write(_encode_manifest(data))
    os.replace(str(temporary), str(path))


def _copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(destination))


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_components(manifest):
    """Return normalized component records, including legacy manifests."""
    if not isinstance(manifest, dict):
        return []
    records = manifest.get("components")
    if isinstance(records, list):
        normalized = []
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                continue
            normalized.append({
                "id": record["id"],
                "name": record.get("name", record["id"]),
                "version": record.get("version"),
                "dependencies": [
                    value for value in record.get("dependencies", [])
                    if isinstance(value, str)
                ],
                "required": bool(record.get("required", False)),
                "remove_directories_on_uninstall": [
                    value for value in record.get(
                        "remove_directories_on_uninstall", []
                    ) if isinstance(value, str)
                ],
            })
        if normalized:
            return normalized
    return [
        {
            "id": component_id,
            "name": component_id,
            "dependencies": [],
            "required": False,
            "remove_directories_on_uninstall": [],
        }
        for component_id in manifest.get("selected_components", [])
        if isinstance(component_id, str)
    ]


def installed_component_versions(manifest):
    """Return installed component IDs mapped to their recorded versions."""
    return {
        component["id"]: component.get("version")
        for component in _manifest_components(manifest)
    }


def dependent_removal_closure(manifest, selected_components):
    """Include installed dependents that cannot remain without selected items."""
    selected = set(selected_components)
    components = _manifest_components(manifest)
    changed = True
    while changed:
        changed = False
        for component in components:
            if component["id"] in selected:
                continue
            if any(
                dependency in selected
                for dependency in component["dependencies"]
            ):
                selected.add(component["id"])
                changed = True
    return selected


def uninstall_selection_status(manifest, selected_components):
    """Describe a component-removal selection for UI summaries."""
    components = _manifest_components(manifest)
    selected = set(selected_components)
    core_component = manifest.get("core_component")
    if not isinstance(core_component, str):
        core_component = components[0]["id"] if components else None
    selected_names = [
        component["name"] for component in components
        if component["id"] in selected
    ]
    return {
        "selected_count": len(selected_names),
        "total_count": len(components),
        "selected_names": selected_names,
        "core_selected": core_component in selected,
    }


class InstallRecorder:
    """Record an installation transaction and retain originals for uninstall."""

    def __init__(self, install_root, installer_metadata, components, uninstaller,
                 core_component=None):
        self.install_root = Path(install_root).resolve()
        self.data_directory = self.install_root / INSTALL_DATA_DIRECTORY
        self.data_directory_preexisted = self.data_directory.exists()
        self.manifest_path = self.data_directory / INSTALL_MANIFEST_NAME
        self.backup_directory = self.data_directory / "backups"
        transaction_name = "{}-{}".format(
            datetime.now().strftime("%Y%m%d%H%M%S%f"), os.getpid()
        )
        self.transaction_directory = (
            self.data_directory / "transactions" / transaction_name
        )
        self.installer_metadata = dict(installer_metadata)
        self.components = []
        for component in components:
            if isinstance(component, dict):
                self.components.append({
                    "id": component["id"],
                    "name": component.get("name", component["id"]),
                    "version": component.get("version"),
                    "dependencies": list(component.get("dependencies", [])),
                    "required": bool(component.get("required", False)),
                    "remove_directories_on_uninstall": list(
                        component.get("remove_directories_on_uninstall", [])
                    ),
                })
            else:
                self.components.append({
                    "id": component,
                    "name": component,
                    "version": None,
                    "dependencies": [],
                    "required": False,
                    "remove_directories_on_uninstall": [],
                })
        self.component_ids = [component["id"] for component in self.components]
        self.core_component = core_component or (
            self.component_ids[0] if self.component_ids else None
        )
        self.uninstaller = dict(uninstaller)
        self.previous_manifest = self._load_previous_manifest()
        self.files = {
            entry["path"]: dict(entry)
            for entry in self.previous_manifest.get("files", [])
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        }
        self.created_directories = set(
            path
            for path in self.previous_manifest.get("created_directories", [])
            if isinstance(path, str)
        )
        self.transaction_files = {}
        self.transaction_directories = []
        self.new_backups = []
        self.registry = self.previous_manifest.get("windows_registry")
        self.uninstaller_ui = self.previous_manifest.get("uninstaller_ui")
        self.current_component = None
        self.touched_files = {}
        self.skipped_files = 0

        previous_components = _manifest_components(self.previous_manifest)
        components_by_id = {
            component["id"]: component for component in previous_components
        }
        components_by_id.update({
            component["id"]: component for component in self.components
        })
        self.components = list(components_by_id.values())
        self.component_ids = [component["id"] for component in self.components]

        previous_ids = [
            component["id"] for component in previous_components
        ]
        for entry in self.files.values():
            owners = entry.get("components")
            if not isinstance(owners, list):
                entry["components"] = list(previous_ids)

    def begin_component(self, component_id):
        if component_id not in self.component_ids:
            raise ValueError("组件不属于当前安装: {}".format(component_id))
        self.current_component = component_id
        self.touched_files[component_id] = set()

    def finish_component(self, component_id):
        """Remove files that belonged to an older version of this component."""
        touched = self.touched_files.get(component_id, set())
        stale = [
            relative for relative, entry in self.files.items()
            if component_id in entry.get("components", [])
            and relative not in touched
        ]
        for relative in stale:
            entry = self.files[relative]
            entry["components"] = [
                owner for owner in entry.get("components", [])
                if owner != component_id
            ]
            if entry["components"]:
                continue
            if entry.get("managed", True):
                self._snapshot_file(relative)
                target = self.install_root / Path(relative)
                if target.is_symlink():
                    raise ValueError("拒绝删除替换了旧版文件的符号链接: {}".format(target))
                if target.is_file():
                    target.unlink()
                elif target.exists():
                    raise OSError("旧版组件文件已变成目录: {}".format(target))
                backup = entry.get("backup")
                if backup:
                    _copy_file(self.data_directory / Path(backup), target)
            del self.files[relative]

    def _snapshot_file(self, relative):
        if relative in self.transaction_files:
            return
        path = self.install_root / Path(relative)
        existed = path.is_file()
        transaction_backup = None
        if existed:
            transaction_backup = self.transaction_directory / relative
            _copy_file(path, transaction_backup)
        self.transaction_files[relative] = {
            "existed": existed,
            "snapshot": (
                transaction_backup.relative_to(self.data_directory).as_posix()
                if transaction_backup is not None
                else None
            ),
        }

    def _load_previous_manifest(self):
        if not self.manifest_path.is_file():
            return {}
        try:
            data = _decode_manifest(self.manifest_path.read_bytes())
        except (OSError, ValueError) as error:
            raise RuntimeError("无法读取已有安装信息: {}".format(error)) from error
        if not isinstance(data, dict):
            raise ValueError("已有安装信息格式无效")
        return data

    def _relative_path(self, path):
        path = Path(path).resolve()
        root = self.install_root.resolve()
        try:
            relative = path.relative_to(root)
        except ValueError:
            raise ValueError("安装目标位于安装目录之外: {}".format(path))
        if not relative.parts or relative.parts[0] == INSTALL_DATA_DIRECTORY:
            raise ValueError("安装内容不能写入安装信息目录: {}".format(path))

        resolved_parent = path.parent.resolve()
        if not _is_relative_to(resolved_parent, self.install_root):
            raise ValueError("安装目标通过链接指向安装目录之外: {}".format(path))
        return relative.as_posix()

    def prepare_directory(self, directory):
        directory = Path(directory).resolve()
        if directory == self.install_root:
            return
        self._relative_path(directory / ".directory-check")
        missing = []
        current = directory
        while current != self.install_root and not current.exists():
            missing.append(current)
            current = current.parent
        if current != self.install_root and not current.is_dir():
            raise ValueError("安装目标的父路径不是目录: {}".format(current))
        directory.mkdir(parents=True, exist_ok=True)
        for created in reversed(missing):
            relative = created.relative_to(self.install_root).as_posix()
            if relative not in self.created_directories:
                self.created_directories.add(relative)
            if relative not in self.transaction_directories:
                self.transaction_directories.append(relative)

    def prepare_file(self, path):
        path = Path(path).absolute()
        if path.is_symlink():
            raise ValueError("拒绝覆盖符号链接: {}".format(path))
        path = path.resolve()
        relative = self._relative_path(path)
        if relative in self.transaction_files:
            self._record_file_owner(relative)
            return
        if path.exists() and not path.is_file():
            raise ValueError("文件安装目标已被目录占用: {}".format(path))

        self.prepare_directory(path.parent)
        existed = path.is_file()
        self._snapshot_file(relative)

        if relative not in self.files:
            original_backup = None
            if existed:
                original_backup = self.backup_directory / relative
                _copy_file(path, original_backup)
                self.new_backups.append(original_backup)
            self.files[relative] = {
                "path": relative,
                "backup": (
                    original_backup.relative_to(self.data_directory).as_posix()
                    if original_backup is not None
                    else None
                ),
                "components": [],
                "managed": True,
            }
        elif not self.files[relative].get("managed", True):
            original_backup = self.backup_directory / relative
            if existed:
                _copy_file(path, original_backup)
                self.new_backups.append(original_backup)
                self.files[relative]["backup"] = (
                    original_backup.relative_to(self.data_directory).as_posix()
                )
            self.files[relative]["managed"] = True
        self._record_file_owner(relative)

    def _record_file_owner(self, relative):
        if self.current_component is None:
            return
        owners = self.files[relative].setdefault("components", [])
        if self.current_component not in owners:
            owners.append(self.current_component)
        self.touched_files.setdefault(self.current_component, set()).add(relative)

    def install_file(self, source, destination):
        """Install one file, skipping writes when its content is unchanged."""
        source = Path(source)
        destination = Path(destination)
        source_digest = _file_digest(source)
        destination_digest = None
        if destination.is_file() and not destination.is_symlink():
            destination_digest = _file_digest(destination)
        if source_digest == destination_digest:
            relative = self._relative_path(destination)
            if relative not in self.files:
                self.files[relative] = {
                    "path": relative,
                    "backup": None,
                    "components": [],
                    "managed": False,
                }
            self.files[relative]["sha256"] = source_digest
            self._record_file_owner(relative)
            self.skipped_files += 1
            return False

        self.prepare_file(destination)
        _copy_file(source, destination)
        relative = self._relative_path(destination)
        self.files[relative]["sha256"] = source_digest
        self.files[relative]["managed"] = True
        return True

    def set_registry(self, registry):
        self.registry = dict(registry) if registry else None

    def store_uninstaller_ui(self, configuration):
        """Copy standalone uninstaller UI assets into the private data folder."""
        configuration = dict(configuration or {})
        assets = configuration.pop("assets", {})
        stored_assets = {}
        ui_directory = self.data_directory / "ui"
        for role, source_value in assets.items():
            if role not in {"license", "sidebar", "header", "icon"}:
                continue
            source = Path(source_value).resolve()
            if not source.is_file():
                continue
            suffix = source.suffix.lower()
            if not suffix or not suffix[1:].isalnum():
                suffix = ".dat"
            target = ui_directory / (role + suffix)
            _copy_file(source, target)
            stored_assets[role] = target.relative_to(
                self.data_directory
            ).as_posix()
        configuration["assets"] = stored_assets
        self.uninstaller_ui = configuration
        return configuration

    def estimated_size(self):
        total = 0
        for relative in self.files:
            path = self.install_root / Path(relative)
            try:
                total += path.stat().st_size
            except OSError:
                pass
        return total

    def finalize(self):
        manifest = {
            "schema_version": 2,
            "program_name": self.installer_metadata["program_name"],
            "version": self.installer_metadata["version"],
            "publisher": self.installer_metadata["author"],
            "installed_at": datetime.now().astimezone().isoformat(),
            "install_root": str(self.install_root),
            "selected_components": self.component_ids,
            "components": self.components,
            "core_component": self.core_component,
            "uninstaller": self.uninstaller,
            "files": [self.files[key] for key in sorted(self.files)],
            "created_directories": sorted(
                self.created_directories,
                key=lambda value: (len(Path(value).parts), value),
            ),
            "windows_registry": self.registry,
            "uninstaller_ui": self.uninstaller_ui,
        }
        _atomic_write_manifest(self.manifest_path, manifest)
        self._discard_transaction()

    def rollback(self):
        for relative, state in reversed(list(self.transaction_files.items())):
            target = self.install_root / Path(relative)
            try:
                if target.is_symlink() or target.is_file():
                    target.unlink()
                if state["existed"]:
                    snapshot = self.data_directory / Path(state["snapshot"])
                    _copy_file(snapshot, target)
            except OSError:
                pass
        for relative in reversed(self.transaction_directories):
            try:
                (self.install_root / Path(relative)).rmdir()
            except OSError:
                pass
        for backup in self.new_backups:
            try:
                backup.unlink()
            except OSError:
                pass
        self._discard_transaction()
        if not self.previous_manifest and not self.data_directory_preexisted:
            shutil.rmtree(str(self.data_directory), ignore_errors=True)

    def _discard_transaction(self):
        shutil.rmtree(str(self.transaction_directory), ignore_errors=True)
        transactions = self.data_directory / "transactions"
        try:
            transactions.rmdir()
        except OSError:
            pass


def register_windows_uninstaller(metadata, install_root, executable, estimated_size):
    if platform.system().lower() != "windows":
        return None
    import winreg

    product_key_path = _validate_registry_path(
        metadata["registry_key"], "registry_key"
    )
    uninstall_key_path = _validate_registry_path(
        metadata["uninstall_registry_key"], "uninstall_registry_key"
    )
    if product_key_path.casefold() == uninstall_key_path.casefold():
        raise ValueError("registry_key 与 uninstall_registry_key 不能相同")
    executable = str(Path(executable).resolve())
    manifest = str(
        Path(install_root).resolve() / INSTALL_DATA_DIRECTORY / INSTALL_MANIFEST_NAME
    )
    uninstall_command = subprocess.list2cmdline(
        [executable, "--manifest", manifest]
    )
    uninstall_values = {
        "DisplayName": metadata["program_name"],
        "DisplayVersion": metadata["version"],
        "Publisher": metadata["author"],
        "InstallLocation": str(Path(install_root).resolve()),
        "DisplayIcon": executable,
        "UninstallString": uninstall_command,
    }
    access = winreg.KEY_WRITE | getattr(winreg, "KEY_WOW64_32KEY", 0)
    errors = []
    for hive_name, hive in (("HKLM", winreg.HKEY_LOCAL_MACHINE), ("HKCU", winreg.HKEY_CURRENT_USER)):
        try:
            with winreg.CreateKeyEx(hive, product_key_path, 0, access) as key:
                winreg.SetValueEx(
                    key, "InstallLocation", 0, winreg.REG_SZ,
                    str(Path(install_root).resolve()),
                )
                winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, metadata["version"])
                winreg.SetValueEx(key, "Uninstaller", 0, winreg.REG_SZ, executable)
            with winreg.CreateKeyEx(hive, uninstall_key_path, 0, access) as key:
                for name, value in uninstall_values.items():
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(
                    key,
                    "EstimatedSize",
                    0,
                    winreg.REG_DWORD,
                    min(max(int(estimated_size // 1024), 0), 0xFFFFFFFF),
                )
            return {
                "hive": hive_name,
                "product_key": product_key_path,
                "uninstall_key": uninstall_key_path,
                "view": "32",
            }
        except OSError as error:
            _delete_windows_registry_paths(
                hive, (uninstall_key_path, product_key_path), access
            )
            errors.append("{}: {}".format(hive_name, error))
    raise OSError("无法写入 Windows 卸载注册表项: {}".format("; ".join(errors)))


def _validate_registry_path(value, field_name):
    path = value.strip().strip("\\")
    parts = [part for part in path.split("\\") if part]
    if len(parts) < 2 or parts[0].casefold() != "software" or "/" in value:
        raise ValueError(
            "{} 必须是 Software\\... 下的完整注册表路径".format(field_name)
        )
    return "\\".join(parts)


def _delete_windows_registry_paths(hive, paths, access):
    import winreg

    view = access & (
        getattr(winreg, "KEY_WOW64_32KEY", 0)
        | getattr(winreg, "KEY_WOW64_64KEY", 0)
    )
    for key_path in paths:
        try:
            delete_key_ex = getattr(winreg, "DeleteKeyEx", None)
            if delete_key_ex is not None:
                delete_key_ex(hive, key_path, view, 0)
            else:
                winreg.DeleteKey(hive, key_path)
        except OSError:
            pass


def remove_windows_uninstall_entry(registry=None):
    if platform.system().lower() != "windows":
        return
    import winreg

    paths = []
    if isinstance(registry, dict):
        paths.extend(
            path
            for path in (registry.get("uninstall_key"), registry.get("product_key"))
            if path
        )
    hives = (("HKLM", winreg.HKEY_LOCAL_MACHINE), ("HKCU", winreg.HKEY_CURRENT_USER))
    views = (
        getattr(winreg, "KEY_WOW64_32KEY", 0),
        getattr(winreg, "KEY_WOW64_64KEY", 0),
    )
    preferred_hive = registry.get("hive") if isinstance(registry, dict) else None
    ordered_hives = sorted(hives, key=lambda item: item[0] != preferred_hive)
    for _, hive in ordered_hives:
        for view in dict.fromkeys(views):
            _delete_windows_registry_paths(hive, paths, winreg.KEY_WRITE | view)


def load_manifest(manifest_path=None):
    path = (
        Path(manifest_path).resolve()
        if manifest_path
        else resolve_application_directory(
            __file__,
            frozen=bool(getattr(sys, "frozen", False) or "__compiled__" in globals()),
        ) / INSTALL_DATA_DIRECTORY / INSTALL_MANIFEST_NAME
    )
    try:
        manifest = _decode_manifest(path.read_bytes())
    except (OSError, ValueError) as error:
        raise RuntimeError("无法读取安装信息 {}: {}".format(path, error)) from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in (1, 2):
        raise ValueError("安装信息格式不受支持")
    install_root = Path(manifest.get("install_root", "")).resolve()
    expected_path = install_root / INSTALL_DATA_DIRECTORY / INSTALL_MANIFEST_NAME
    if path != expected_path:
        raise ValueError("安装信息路径与安装目录不匹配")
    return path, manifest


def _current_uninstaller_container(install_root):
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        appimage_path = Path(appimage).resolve()
        if _is_relative_to(appimage_path, install_root):
            return appimage_path
    executable = Path(sys.executable).resolve()
    if not _is_relative_to(executable, install_root):
        return None
    for parent in (executable, *executable.parents):
        if parent == install_root:
            break
        if parent.suffix.lower() == ".app":
            return parent
    return executable


def _resolve_uninstall_directory(install_root, configured_path):
    root = Path(install_root).absolute()
    value = configured_path.replace("{install_path}", str(root))
    value = value.replace("\\", os.sep).replace("/", os.sep)
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = Path(os.path.abspath(str(path)))
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError("拒绝删除安装目录之外的目录: {}".format(path))
    if not relative.parts or relative.parts[0] == INSTALL_DATA_DIRECTORY:
        raise ValueError("拒绝删除安装根目录或安装信息目录: {}".format(path))
    try:
        path.parent.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError("卸载目录通过链接指向安装目录之外: {}".format(path))
    return path


def _empty_parent_directories(path, install_root):
    """Yield removable parents below the installation root."""
    root = Path(install_root).absolute()
    current = Path(path).absolute().parent
    while current != root:
        try:
            current.relative_to(root)
        except ValueError:
            break
        if current.name == INSTALL_DATA_DIRECTORY:
            break
        yield current
        current = current.parent


def _remove_empty_directories(install_root, directories, deferred=None):
    """Remove safe empty directories, retaining non-empty/user-owned folders."""
    root = Path(install_root).resolve()
    data_directory = root / INSTALL_DATA_DIRECTORY
    errors = []
    for directory in sorted(
        {Path(value).absolute() for value in directories},
        key=lambda value: len(value.parts),
        reverse=True,
    ):
        if directory in (root, data_directory):
            continue
        try:
            directory.relative_to(root)
            directory.resolve().relative_to(root)
        except (OSError, ValueError):
            errors.append("拒绝删除安装目录之外的目录: {}".format(directory))
            continue
        if deferred is not None and (
            directory == deferred or _is_relative_to(directory, deferred)
        ):
            continue
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError as error:
            if error.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR):
                errors.append("{}: {}".format(directory, error))
    return errors


def uninstall(manifest_path, manifest, selected_components=None):
    install_root = Path(manifest["install_root"]).resolve()
    data_directory = install_root / INSTALL_DATA_DIRECTORY
    deferred = _current_uninstaller_container(install_root)
    errors = []

    components = _manifest_components(manifest)
    installed_ids = {component["id"] for component in components}
    if selected_components is None:
        selected = set(installed_ids)
    else:
        selected = set(selected_components)
        unknown = selected - installed_ids
        if unknown:
            return ["安装信息中不存在组件: {}".format(
                ", ".join(sorted(unknown))
            )], deferred
    if not selected:
        return ["没有选择要卸载的组件"], deferred
    remaining_ids = installed_ids - selected
    remaining_components = [
        component for component in components
        if component["id"] in remaining_ids
    ]
    legacy_owners = [component["id"] for component in components]
    retained_entries = []
    removed_backups = []
    deferred_removal_requested = False
    empty_directory_candidates = set()

    entries = [entry for entry in manifest.get("files", []) if isinstance(entry, dict)]
    entries.sort(key=lambda entry: len(Path(entry.get("path", "")).parts), reverse=True)
    for entry in entries:
        relative = entry.get("path")
        if not isinstance(relative, str):
            errors.append("安装信息包含无效文件路径")
            continue
        owners = entry.get("components")
        if not isinstance(owners, list):
            owners = legacy_owners
        owners = [owner for owner in owners if owner not in selected]
        if owners:
            retained = dict(entry)
            retained["components"] = owners
            retained_entries.append(retained)
            continue

        if not entry.get("managed", True):
            continue
        target = (install_root / Path(relative)).absolute()
        try:
            target.relative_to(install_root.absolute())
        except ValueError:
            errors.append("拒绝删除安装目录之外的路径: {}".format(target))
            continue
        if deferred is not None and (
            target == deferred or _is_relative_to(target, deferred)
        ):
            deferred_removal_requested = True
            continue
        try:
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.exists():
                raise OSError("目标已变成目录")
            backup = entry.get("backup")
            if backup:
                backup_path = (data_directory / Path(backup)).resolve()
                if not _is_relative_to(backup_path, data_directory.resolve()):
                    raise ValueError("备份路径超出安装信息目录")
                if not backup_path.is_file():
                    raise FileNotFoundError("备份文件不存在: {}".format(backup_path))
                _copy_file(backup_path, target)
                removed_backups.append(backup_path)
            empty_directory_candidates.update(
                _empty_parent_directories(target, install_root)
            )
        except (OSError, ValueError) as error:
            errors.append("{}: {}".format(target, error))

    if not errors:
        configured_directories = {
            value
            for component in components
            if component["id"] in selected
            for value in component.get("remove_directories_on_uninstall", [])
        }
        resolved_directories = []
        for configured_path in configured_directories:
            try:
                resolved_directories.append(
                    _resolve_uninstall_directory(install_root, configured_path)
                )
            except ValueError as error:
                errors.append(str(error))
        for directory in sorted(
            resolved_directories,
            key=lambda value: len(value.parts),
            reverse=True,
        ):
            try:
                if directory.is_symlink():
                    directory.unlink()
                elif directory.is_dir():
                    shutil.rmtree(str(directory))
                elif directory.exists():
                    raise OSError("卸载目录目标不是目录")
            except OSError as error:
                errors.append("{}: {}".format(directory, error))
            empty_directory_candidates.update(
                _empty_parent_directories(directory, install_root)
            )

    for relative in manifest.get("created_directories", []):
        directory = (install_root / Path(relative)).absolute()
        empty_directory_candidates.add(directory)
        empty_directory_candidates.update(
            _empty_parent_directories(directory, install_root)
        )
    errors.extend(_remove_empty_directories(
        install_root, empty_directory_candidates, deferred
    ))

    if errors:
        return errors, deferred

    core_component = manifest.get("core_component")
    if not isinstance(core_component, str):
        core_component = components[0]["id"] if components else None
    core_removed = core_component in selected
    if core_removed or not remaining_ids:
        remove_windows_uninstall_entry(manifest.get("windows_registry"))

    if remaining_ids and not core_removed:
        updated_manifest = dict(manifest)
        updated_manifest.update({
            "schema_version": 2,
            "selected_components": [
                component["id"] for component in remaining_components
            ],
            "components": remaining_components,
            "files": sorted(retained_entries, key=lambda entry: entry["path"]),
            "windows_registry": (
                None if core_removed else manifest.get("windows_registry")
            ),
        })
        try:
            _atomic_write_manifest(Path(manifest_path), updated_manifest)
            for backup in removed_backups:
                try:
                    backup.unlink()
                except OSError:
                    pass
        except OSError as error:
            errors.append("无法更新安装信息: {}".format(error))
        return errors, deferred if deferred_removal_requested else None

    try:
        shutil.rmtree(str(data_directory))
    except OSError as error:
        errors.append("无法删除安装信息: {}".format(error))
    return errors, deferred


def remove_running_uninstaller(path):
    if path is None:
        return
    if platform.system().lower() == "windows":
        target = str(Path(path).resolve()).replace("'", "''")
        target_literal = "'{}'".format(target)
        cleanup_script = (
            "$ErrorActionPreference = 'SilentlyContinue'; "
            "Wait-Process -Id {pid}; "
            "for ($attempt = 0; $attempt -lt 40; $attempt++) {{ "
            "Remove-Item -LiteralPath {target} -Force; "
            "if (-not (Test-Path -LiteralPath {target})) {{ exit 0 }}; "
            "Start-Sleep -Milliseconds 250 "
            "}}; exit 1"
        ).format(pid=os.getpid(), target=target_literal)
        encoded_script = base64.b64encode(
            cleanup_script.encode("utf-16le")
        ).decode("ascii")
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-WindowStyle", "Hidden", "-EncodedCommand", encoded_script,
            ],
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    elif path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()


def resolve_uninstaller_ui_asset(manifest_path, manifest, role):
    """Resolve a recorded UI asset without allowing paths outside private data."""
    configuration = manifest.get("uninstaller_ui")
    if not isinstance(configuration, dict):
        return None
    assets = configuration.get("assets")
    if not isinstance(assets, dict) or not isinstance(assets.get(role), str):
        return None
    data_directory = Path(manifest_path).resolve().parent
    candidate = (data_directory / Path(assets[role])).resolve()
    if not _is_relative_to(candidate, data_directory) or not candidate.is_file():
        return None
    return candidate


def create_uninstaller_window(manifest_path, manifest):
    """Create the branded wizard window; the caller owns the QApplication."""
    try:
        from PySide6.QtCore import Qt, QThread, Signal, QTimer
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QFrame, QGroupBox, QHeaderView,
            QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
            QPushButton, QSizePolicy, QStackedWidget, QTextEdit, QTreeWidget,
            QTreeWidgetItem, QVBoxLayout, QWidget,
        )
    except ImportError:
        from PySide2.QtCore import Qt, QThread, Signal, QTimer
        from PySide2.QtGui import QIcon, QPixmap
        from PySide2.QtWidgets import (
            QApplication, QCheckBox, QFrame, QGroupBox, QHeaderView,
            QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
            QPushButton, QSizePolicy, QStackedWidget, QTextEdit, QTreeWidget,
            QTreeWidgetItem, QVBoxLayout, QWidget,
        )
    components = _manifest_components(manifest)
    components_by_id = {component["id"]: component for component in components}
    program_name = manifest.get("program_name", "程序")
    ui_configuration = manifest.get("uninstaller_ui")
    if not isinstance(ui_configuration, dict):
        ui_configuration = {}
    product_name = ui_configuration.get("product_name", program_name)
    footer_text = ui_configuration.get("footer_text", "Universal Installer")
    core_component = manifest.get("core_component")
    ResponsiveImageLabel = responsive_image_label_class(
        Qt, QLabel, QPixmap, QSizePolicy
    )

    class UninstallWorker(QThread):
        progress_updated = Signal(int, str)
        completed = Signal(object, object)

        def __init__(self, selected):
            super().__init__()
            self.selected = set(selected)

        def run(self):
            self.progress_updated.emit(10, "正在分析已安装文件...")
            errors, deferred = uninstall(
                manifest_path, manifest, self.selected
            )
            self.progress_updated.emit(
                100 if not errors else 0,
                "卸载完成" if not errors else "卸载过程中出现错误",
            )
            self.completed.emit(errors, deferred)

    class UninstallerWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("卸载 {}".format(product_name))
            configure_responsive_window(
                self, QApplication,
                minimum_size=(640, 480),
                default_size=(760, 560),
                maximum_size=(920, 680),
                screen_ratio=(0.72, 0.78),
            )
            icon = resolve_uninstaller_ui_asset(
                manifest_path, manifest, "icon"
            )
            if icon is not None:
                self.setWindowIcon(QIcon(str(icon)))
            self.components = components
            self.items_by_id = {}
            self.selected_components = set()
            self.worker = None
            self.success = False
            self.page_layouts = []
            self.header_images = []
            self.sidebar_image = None
            self.stacked = QStackedWidget()
            self.setCentralWidget(self.stacked)
            self.pages = {
                "welcome": self.build_welcome_page(),
                "license": self.build_license_page(),
                "components": self.build_components_page(),
                "progress": self.build_progress_page(),
                "finish": self.build_finish_page(),
            }
            for page in self.pages.values():
                self.stacked.addWidget(page)
            self.apply_style()
            self.go_to_page("welcome")
            QTimer.singleShot(0, self.apply_native_windows_effects)

        def apply_style(self):
            self.windows_style_profile = windows_style_profile()
            self.windows_theme = windows_app_theme()

        def apply_native_windows_effects(self):
            apply_windows_window_effects(
                self, self.windows_theme, self.windows_style_profile
            )

        def page_shell(self, title, subtitle, include_header=True):
            page = QWidget()
            layout = QVBoxLayout(page)
            self.page_layouts.append(layout)
            if include_header:
                header_asset = resolve_uninstaller_ui_asset(
                    manifest_path, manifest, "header"
                )
                if header_asset is not None:
                    header = ResponsiveImageLabel(
                        header_asset, QSizePolicy.Fixed
                    )
                    self.header_images.append(header)
                    layout.addWidget(header)
            title_label = QLabel(title)
            title_font = title_label.font()
            title_font.setPointSize(max(14, title_font.pointSize() + 4))
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_label.setAlignment(Qt.AlignCenter)
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            layout.addWidget(subtitle_label)
            content_layout = QVBoxLayout()
            layout.addLayout(content_layout, 1)
            button_layout = QHBoxLayout()
            button_layout.setSpacing(8)
            button_layout.addStretch(1)
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            layout.addWidget(separator)
            layout.addLayout(button_layout)
            footer = QLabel(footer_text)
            footer.setAlignment(Qt.AlignCenter)
            footer_font = footer.font()
            footer_font.setPointSize(max(8, footer_font.pointSize() - 1))
            footer.setFont(footer_font)
            layout.addWidget(footer)
            self.update_responsive_layout()
            return page, content_layout, button_layout

        @staticmethod
        def add_button(layout, text, callback, primary=False):
            return add_wizard_button(
                QPushButton, layout, text, callback, primary=primary
            )

        def build_welcome_page(self):
            page, content, buttons = self.page_shell(
                "{} 卸载程序".format(product_name),
                "此向导将帮助你移除已安装的组件。",
                include_header=False,
            )
            body = QHBoxLayout()
            sidebar_asset = resolve_uninstaller_ui_asset(
                manifest_path, manifest, "sidebar"
            )
            if sidebar_asset is not None:
                self.sidebar_image = ResponsiveImageLabel(
                    sidebar_asset, QSizePolicy.Expanding
                )
                body.addWidget(self.sidebar_image, 2)
            message = QLabel(
                "将保留未选择的组件和共享文件。\n\n"
                "点击[下一步(N)]阅读许可证并继续。"
            )
            message.setWordWrap(True)
            message.setAlignment(Qt.AlignCenter)
            body.addWidget(message, 3)
            content.addLayout(body)
            self.add_button(buttons, "取消(C)", self.cancel_uninstall)
            self.add_button(
                buttons, "下一步(N)",
                lambda: self.go_to_page("license"), True
            )
            return page

        def build_license_page(self):
            page, content, buttons = self.page_shell(
                program_name,
                "卸载 {} 之前，请阅读许可证条款。".format(product_name),
            )
            group = QGroupBox("许可证协议")
            group_layout = QVBoxLayout(group)
            self.license_text = QTextEdit()
            self.license_text.setReadOnly(True)
            license_asset = resolve_uninstaller_ui_asset(
                manifest_path, manifest, "license"
            )
            if license_asset is None:
                license_contents = "许可证文件未随此安装记录保存。"
            else:
                try:
                    license_contents = license_asset.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as error:
                    license_contents = "无法读取许可证：{}".format(error)
            self.license_text.setPlainText(license_contents)
            group_layout.addWidget(self.license_text)
            self.license_checkbox = QCheckBox("我已阅读许可证条款")
            group_layout.addWidget(self.license_checkbox)
            content.addWidget(group)
            self.add_button(
                buttons, "< 上一步(P)", lambda: self.go_to_page("welcome")
            )
            self.license_next = self.add_button(
                buttons, "下一步(N)", lambda: self.go_to_page("components"), True
            )
            self.license_next.setEnabled(False)
            self.license_checkbox.stateChanged.connect(
                lambda _state: self.license_next.setEnabled(
                    self.license_checkbox.isChecked()
                )
            )
            self.add_button(buttons, "取消(C)", self.cancel_uninstall)
            return page

        def build_components_page(self):
            page, content, buttons = self.page_shell(
                program_name,
                "选择要卸载的组件。依赖所选组件的项目也必须一起卸载。",
            )
            self.component_tree = QTreeWidget()
            self.component_tree.setHeaderLabels(("组件", "已安装版本", "依赖"))
            self.component_tree.setAlternatingRowColors(True)
            self.component_tree.setRootIsDecorated(False)
            header = self.component_tree.header()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.Stretch)
            for component in components:
                item = QTreeWidgetItem(self.component_tree)
                name = component["name"]
                if component["id"] == core_component:
                    name += " (核心)"
                item.setText(0, name)
                item.setText(1, component.get("version") or "—")
                dependency_names = [
                    components_by_id[value]["name"]
                    for value in component["dependencies"]
                    if value in components_by_id
                ]
                item.setText(2, ", ".join(dependency_names) or "—")
                item.setData(0, Qt.UserRole, component["id"])
                item.setCheckState(0, Qt.Unchecked)
                self.items_by_id[component["id"]] = item
            self.component_tree.itemChanged.connect(self.on_component_changed)
            selection_tools = QHBoxLayout()
            selection_tools.setSpacing(8)
            self.selection_summary = QLabel()
            self.selection_summary.setWordWrap(True)
            selection_tools.addWidget(self.selection_summary, 1)
            select_all = QPushButton("全部选择")
            select_all.clicked.connect(self.select_all_components)
            selection_tools.addWidget(select_all)
            clear_all = QPushButton("清除选择")
            clear_all.clicked.connect(self.clear_component_selection)
            selection_tools.addWidget(clear_all)
            content.addLayout(selection_tools)
            content.addWidget(self.component_tree)
            self.core_removal_warning = QLabel(
                "⚠ 移除核心组件也会删除卸载器、Windows "
                "注册项和全部安装记录。"
            )
            self.core_removal_warning.setWordWrap(True)
            self.core_removal_warning.setVisible(False)
            content.addWidget(self.core_removal_warning)
            self.add_button(
                buttons, "< 上一步(P)", lambda: self.go_to_page("license")
            )
            self.add_button(buttons, "卸载(U)", self.confirm_uninstall, True)
            self.add_button(buttons, "取消(C)", self.cancel_uninstall)
            self.update_component_summary()
            return page

        def build_progress_page(self):
            page, content, _buttons = self.page_shell(
                "正在卸载 {}".format(product_name),
                "正在移除所选组件，请稍候...",
            )
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_log = QTextEdit()
            self.progress_log.setReadOnly(True)
            content.addWidget(self.progress_bar)
            content.addWidget(self.progress_log, 1)
            return page

        def build_finish_page(self):
            page, content, buttons = self.page_shell(
                "卸载结果", "卸载操作尚未运行。"
            )
            self.finish_message = QLabel()
            self.finish_message.setWordWrap(True)
            self.finish_message.setAlignment(Qt.AlignCenter)
            finish_font = self.finish_message.font()
            finish_font.setBold(True)
            self.finish_message.setFont(finish_font)
            content.addStretch(1)
            content.addWidget(self.finish_message)
            content.addStretch(1)
            self.add_button(buttons, "完成(F)", self.close, True)
            return page

        def selected_component_ids(self):
            return {
                component_id for component_id, item in self.items_by_id.items()
                if item.checkState(0) == Qt.Checked
            }

        def set_component_selection(self, selected):
            with_selection = set(selected)
            self.component_tree.blockSignals(True)
            try:
                for component_id, item in self.items_by_id.items():
                    item.setCheckState(
                        0, Qt.Checked
                        if component_id in with_selection else Qt.Unchecked
                    )
            finally:
                self.component_tree.blockSignals(False)
            self.update_component_summary()

        def select_all_components(self):
            self.set_component_selection(components_by_id)

        def clear_component_selection(self):
            self.set_component_selection(set())

        def update_component_summary(self):
            status = uninstall_selection_status(
                manifest, self.selected_component_ids()
            )
            if status["selected_names"]:
                names = "、".join(status["selected_names"])
                summary = "已选择 {}/{} 个组件：{}".format(
                    status["selected_count"], status["total_count"], names
                )
            else:
                summary = "未选择任何组件。"
            self.selection_summary.setText(summary)
            self.core_removal_warning.setVisible(status["core_selected"])

        def on_component_changed(self, item, _column):
            if self.component_tree.signalsBlocked():
                return
            component_id = item.data(0, Qt.UserRole)
            selected_now = self.selected_component_ids()
            if item.checkState(0) != Qt.Checked:
                affected = [
                    component["name"] for component in components
                    if component["id"] in selected_now
                    and component_id in component["dependencies"]
                ]
                if affected:
                    self.component_tree.blockSignals(True)
                    item.setCheckState(0, Qt.Checked)
                    self.component_tree.blockSignals(False)
                    QMessageBox.information(
                        self, "无法保留依赖组件",
                        "以下已选择组件需要它，不能单独取消：\n\n{}".format(
                            ", ".join(affected)
                        ),
                    )
                self.update_component_summary()
                return
            expanded = dependent_removal_closure(manifest, selected_now)
            added = expanded - selected_now
            if not added:
                self.update_component_summary()
                return
            names = ", ".join(
                self.items_by_id[value].text(0) for value in sorted(added)
            )
            reply = QMessageBox.warning(
                self, "组件依赖警告",
                "以下组件依赖所选组件，也必须一起卸载：\n\n{}\n\n"
                "选择继续会自动勾选它们；选择取消会撤销本次勾选。".format(names),
                QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel,
            )
            self.component_tree.blockSignals(True)
            try:
                if reply == QMessageBox.Ok:
                    for value in added:
                        self.items_by_id[value].setCheckState(0, Qt.Checked)
                else:
                    item.setCheckState(0, Qt.Unchecked)
            finally:
                self.component_tree.blockSignals(False)
            self.update_component_summary()

        def confirm_uninstall(self):
            selected = self.selected_component_ids()
            if not selected:
                QMessageBox.information(self, "未选择组件", "没有选择要卸载的组件。")
                return
            message = (
                "只会移除所选组件独占的文件，共享文件会保留；"
                "安装前被覆盖的文件将恢复。"
            )
            if core_component in selected:
                message += (
                    "\n\n已选择核心组件：卸载器、Windows 注册项和全部安装记录"
                    "也会删除；保留的 BepInEx/模组文件将不再由此工具管理。"
                )
            reply = QMessageBox.question(
                self, "确认卸载", message,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self.selected_components = selected
            self.go_to_page("progress")
            QTimer.singleShot(0, self.start_uninstall)

        def start_uninstall(self):
            self.progress_bar.setValue(0)
            self.progress_log.clear()
            self.worker = UninstallWorker(self.selected_components)
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.completed.connect(self.uninstall_finished)
            self.worker.start()

        def update_progress(self, value, message):
            self.progress_bar.setValue(value)
            self.progress_log.append(message)

        def uninstall_finished(self, errors, deferred):
            errors = list(errors)
            if not errors:
                try:
                    remove_running_uninstaller(deferred)
                except OSError as error:
                    errors.append("无法清理卸载器：{}".format(error))
            self.success = not errors
            if errors:
                self.finish_message.setText(
                    "卸载未完成，安装信息已尽可能保留，可稍后重试：\n\n{}".format(
                        "\n".join(errors[:10])
                    )
                )
            elif core_component in self.selected_components:
                self.finish_message.setText(
                    "核心组件和安装器记录已删除。未选择的 BepInEx/模组文件已保留。"
                )
            elif self.selected_components == set(components_by_id):
                self.finish_message.setText("{} 已成功卸载。".format(product_name))
            else:
                self.finish_message.setText(
                    "所选组件已成功卸载，其他组件和安装信息已保留。"
                )
            self.go_to_page("finish")

        def go_to_page(self, name):
            self.stacked.setCurrentWidget(self.pages[name])

        def update_responsive_layout(self):
            metrics = responsive_ui_metrics(self.width(), self.height())
            for layout in self.page_layouts:
                layout.setContentsMargins(
                    metrics["horizontal_margin"], metrics["vertical_margin"],
                    metrics["horizontal_margin"], metrics["vertical_margin"],
                )
                layout.setSpacing(metrics["spacing"])
            for header in self.header_images:
                header.setFixedHeight(metrics["header_height"])
            if self.sidebar_image is not None:
                self.sidebar_image.setMaximumWidth(metrics["sidebar_width"])

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self.update_responsive_layout()

        def cancel_uninstall(self):
            reply = QMessageBox.question(
                self, "退出卸载", "确定要退出卸载程序吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.close()

        def closeEvent(self, event):
            if self.worker is not None and self.worker.isRunning():
                QMessageBox.warning(
                    self, "卸载进行中", "文件仍在处理中，请等待卸载完成。"
                )
                event.ignore()
                return
            super().closeEvent(event)

    return UninstallerWindow()


def run_gui(manifest_path, manifest):
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        binding = "PySide6"
    except ImportError:
        from PySide2.QtCore import Qt
        from PySide2.QtWidgets import QApplication
        binding = "PySide2"
    configure_high_dpi(QApplication, Qt, binding)
    app = QApplication(sys.argv)
    configure_windows_qt_style(app)
    program_name = manifest.get("program_name", "程序")
    app.setApplicationName("{} 卸载程序".format(program_name))
    app.setApplicationDisplayName("{} 卸载程序".format(program_name))
    window = create_uninstaller_window(manifest_path, manifest)
    window.show()
    execute = getattr(app, "exec", None) or app.exec_
    return execute()


def main():
    parser = argparse.ArgumentParser(description="Universal Installer uninstaller")
    parser.add_argument("--manifest", help="Path to install_info.uim")
    arguments = parser.parse_args()
    try:
        manifest_path, manifest = load_manifest(arguments.manifest)
    except (OSError, RuntimeError, ValueError) as error:
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
        except ImportError:
            from PySide2.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "无法卸载", str(error))
        return 1
    return run_gui(manifest_path, manifest)


if __name__ == "__main__":
    sys.exit(main())
