from __future__ import annotations

import argparse
import ctypes
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

from linux_display import configure_linux_qt_platform

configure_linux_qt_platform()


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


def resolve_application_directory():
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        appimage_path = Path(appimage).resolve()
        if appimage_path.is_file():
            return appimage_path.parent
    launch_file = sys.executable if getattr(sys, "frozen", False) or "__compiled__" in globals() else __file__
    directory = Path(launch_file).resolve().parent
    for parent in (directory, *directory.parents):
        if parent.suffix.lower() == ".app":
            return parent.parent
    return directory


def load_manifest(manifest_path=None):
    path = (
        Path(manifest_path).resolve()
        if manifest_path
        else resolve_application_directory() / INSTALL_DATA_DIRECTORY / INSTALL_MANIFEST_NAME
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
        movefile_delay_until_reboot = 0x4
        result = ctypes.windll.kernel32.MoveFileExW(
            str(path), None, movefile_delay_until_reboot
        )
        if not result:
            raise ctypes.WinError()
    elif path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()


def configure_high_dpi(QApplication, Qt, binding):
    if binding != "PySide2":
        return
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def run_gui(manifest_path, manifest):
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox,
            QTreeWidget, QTreeWidgetItem, QVBoxLayout,
        )
        binding = "PySide6"
    except ImportError:
        from PySide2.QtCore import Qt
        from PySide2.QtWidgets import (
            QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox,
            QTreeWidget, QTreeWidgetItem, QVBoxLayout,
        )
        binding = "PySide2"

    configure_high_dpi(QApplication, Qt, binding)
    app = QApplication(sys.argv)
    program_name = manifest.get("program_name", "程序")
    app.setApplicationName("{} 卸载程序".format(program_name))
    components = _manifest_components(manifest)
    dialog = QDialog()
    dialog.setWindowTitle("卸载 {}".format(program_name))
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("选择要卸载的组件。未选择的组件及共享文件会保留。"))
    tree = QTreeWidget()
    tree.setHeaderLabels(("组件", "版本", "依赖"))
    items_by_id = {}
    for component in components:
        item = QTreeWidgetItem(tree)
        item.setText(0, component["name"])
        item.setText(1, component.get("version") or "—")
        item.setText(2, ", ".join(component["dependencies"]) or "—")
        item.setData(0, Qt.UserRole, component["id"])
        item.setCheckState(0, Qt.Unchecked)
        items_by_id[component["id"]] = item
    tree.resizeColumnToContents(0)
    layout.addWidget(tree)

    changing_selection = [False]

    def selected_component_ids():
        return {
            component_id for component_id, item in items_by_id.items()
            if item.checkState(0) == Qt.Checked
        }

    def on_component_changed(item, _column):
        if changing_selection[0]:
            return
        if item.checkState(0) != Qt.Checked:
            selected_now = selected_component_ids()
            component_id = item.data(0, Qt.UserRole)
            component = next(
                value for value in components if value["id"] == component_id
            )
            if any(
                dependency in selected_now
                for dependency in component["dependencies"]
            ):
                changing_selection[0] = True
                item.setCheckState(0, Qt.Checked)
                changing_selection[0] = False
                QMessageBox.information(
                    dialog,
                    "无法保留依赖组件",
                    "该组件依赖一个已选择卸载的组件。请先取消勾选它的依赖。",
                )
            return
        selected_now = selected_component_ids()
        expanded = dependent_removal_closure(manifest, selected_now)
        added = expanded - selected_now
        if not added:
            return
        names = ", ".join(
            items_by_id[component_id].text(0)
            for component_id in sorted(added)
        )
        reply = QMessageBox.warning(
            dialog,
            "组件依赖警告",
            "以下组件依赖所选组件，也必须一起卸载：\n\n{}\n\n"
            "选择继续会自动勾选它们；选择取消会撤销本次勾选。".format(names),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        changing_selection[0] = True
        try:
            if reply == QMessageBox.Ok:
                for component_id in added:
                    items_by_id[component_id].setCheckState(0, Qt.Checked)
            else:
                item.setCheckState(0, Qt.Unchecked)
        finally:
            changing_selection[0] = False

    tree.itemChanged.connect(on_component_changed)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    execute_dialog = getattr(dialog, "exec", None) or dialog.exec_
    if execute_dialog() != QDialog.Accepted:
        return 0

    selected = selected_component_ids()
    if not selected:
        QMessageBox.information(None, "未选择组件", "没有选择要卸载的组件。")
        return 0
    reply = QMessageBox.question(
        None,
        "确认卸载",
        "只会移除所选组件独占的文件，共享文件会保留；安装前被覆盖的文件将恢复。",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if reply != QMessageBox.Yes:
        return 0

    errors, deferred = uninstall(manifest_path, manifest, selected)
    if errors:
        QMessageBox.critical(
            None,
            "卸载未完成",
            "部分文件无法处理，安装信息已保留，可稍后重试：\n\n{}".format(
                "\n".join(errors[:10])
            ),
        )
        return 1
    all_removed = selected == {component["id"] for component in components}
    message = (
        "{} 已成功卸载。".format(program_name)
        if all_removed
        else "所选组件已成功卸载，其他组件和安装信息已保留。"
    )
    QMessageBox.information(None, "卸载完成", message)
    try:
        remove_running_uninstaller(deferred)
    except OSError as error:
        QMessageBox.warning(None, "清理提示", "卸载器将在稍后清理或需手动删除：{}".format(error))
    return 0


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
