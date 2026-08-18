"""Tests for the core_file extraction-skip feature.

When a component declares ``core_file`` and the core component
(``is_core_component: true``) is not selected, that file must be
excluded during zip extraction.

Since ``main.py`` depends on PySide at import time, these tests
pre-populate ``sys.modules`` with lightweight stubs before importing
the module.
"""

import atexit
import os
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Stub out heavy dependencies before importing main
# ---------------------------------------------------------------------------

# Create a temp dir with metadata.json so main.py's module-level
# get_installer_metadata() call succeeds.
_test_tmp = tempfile.mkdtemp(prefix="bbp_test_")
_test_meta = {
    "program_name": "Test", "short_name": "Test", "version": "1.0",
    "author": "Test", "need_admin": False, "has_uninstaller": False,
    "main_item": 0, "item_metadata": "items.json",
    "registry_key": "Test", "uninstall_registry_key": "Test",
    "footer_info": "", "license_file": "", "left_pic": "",
    "header_pic": "", "icon": "",
    "items": [
        {
            "id": "main", "name": "Core", "version": "1.0",
            "is_core": True, "required": True,
            "dependencies": [], "files": [],
        },
    ],
}
with open(os.path.join(_test_tmp, "metadata.json"), "w", encoding="utf-8") as f:
    import json
    json.dump(_test_meta, f)
# Also write the items metadata file that get_metadata() reads.
with open(os.path.join(_test_tmp, "items.json"), "w", encoding="utf-8") as f:
    json.dump({"items": _test_meta["items"]}, f)
atexit.register(shutil.rmtree, _test_tmp, True)

_pyside6_core = mock.MagicMock()

class _FakeQThread:
    """Minimal QThread stand-in so InstallThread can be defined."""
    progress_updated = mock.MagicMock()
    finished = mock.MagicMock()

    def __init__(self, *a, **kw):
        pass

_pyside6_core.QThread = _FakeQThread
_pyside6_core.Qt = mock.MagicMock()

_STUBS = {
    "PySide6": mock.MagicMock(),
    "PySide6.QtWidgets": mock.MagicMock(),
    "PySide6.QtGui": mock.MagicMock(),
    "PySide6.QtCore": _pyside6_core,
    "PySide2": mock.MagicMock(),
    "PySide2.QtWidgets": mock.MagicMock(),
    "PySide2.QtGui": mock.MagicMock(),
    "PySide2.QtCore": mock.MagicMock(),
    "rarfile": mock.MagicMock(),
    "py7zr": mock.MagicMock(),
    "platform_utils": mock.MagicMock(
        is_frozen_application=lambda globals_: False,
        responsive_image_label_class=lambda *a, **kw: type("Lbl", (), {}),
        responsive_ui_metrics=lambda *a: {
            "header_height": 80, "sidebar_width": 200, "spacing": 8,
        },
        resolve_application_directory=lambda *a, **kw: Path(_test_tmp),
    ),
    "uninstaller": mock.MagicMock(
        INSTALL_DATA_DIRECTORY=".install_data",
        INSTALL_MANIFEST_NAME="manifest.json",
    ),
}

# Ensure the project root is on sys.path so `import main` works.
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

with mock.patch.dict(sys.modules, _STUBS):
    import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip(directory: Path, entries: dict) -> Path:
    """Write a zip containing *entries* ({posix-path: bytes}) and return its path."""
    zpath = directory / "payload.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for rel, data in entries.items():
            zf.writestr(rel, data)
    return zpath


def _build_thread(tmp: Path, core_selected: bool):
    """Create an InstallThread with a recorder that actually copies files."""
    items = [
        {
            "id": "main", "name": "Core", "version": "1.0",
            "is_core": True, "required": True,
            "dependencies": [], "files": [],
        },
        {
            "id": "mod_a", "name": "Mod A", "version": "1.0",
            "required": False, "dependencies": ["main"],
            "files": ["pack/ModA.zip"],
            "core_file": "BepInEx/plugins/ModA.dll",
            "actions": {"pack/ModA.zip": str(tmp / "dest")},
        },
    ]
    meta = {
        "program_name": "Test", "version": "1.0", "author": "Test",
        "short_name": "Test", "need_admin": False, "has_uninstaller": False,
        "main_item": 0, "item_metadata": "items.json",
        "registry_key": "Test", "uninstall_registry_key": "Test",
        "footer_info": "", "license_file": "", "left_pic": "",
        "header_pic": "", "icon": "", "items": items,
    }
    with mock.patch.object(main, "get_metadata", return_value=meta), \
         mock.patch.object(main, "INSTALLER_METADATA", meta), \
         mock.patch.object(main, "get_installer_metadata", return_value=meta):
        thread = main.InstallThread(
            str(tmp / "dest"),
            {"main": core_selected, "mod_a": True},
        )
    # Mock recorder: prepare_directory creates dirs, install_file copies.
    recorder = mock.MagicMock()

    def _prepare_dir(path):
        os.makedirs(path, exist_ok=True)

    def _install_file(source, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))

    recorder.prepare_directory.side_effect = _prepare_dir
    recorder.install_file.side_effect = _install_file
    thread.recorder = recorder
    thread._core_selected = core_selected
    thread.items_by_id = {i["id"]: i for i in items}
    return thread


ZIP_ENTRIES = {
    "BepInEx/plugins/ModA.dll": b"mod-a-binary",
    "BepInEx/plugins/ModA.pdb": b"mod-a-debug",
    "readme.txt": b"hello",
}


# ---------------------------------------------------------------------------
# _extract_archive  – low-level zip filtering
# ---------------------------------------------------------------------------

class ExtractArchiveSkipTests(unittest.TestCase):
    """Test _extract_archive with skip_files for zip archives."""

    def _extract(self, tmp, skip_files=None):
        zpath = _make_zip(tmp, ZIP_ENTRIES)
        thread = _build_thread(tmp, core_selected=True)
        dest = tmp / "dest"
        dest.mkdir()
        thread._extract_archive(str(zpath), "zip", str(dest), skip_files=skip_files)
        return dest

    def test_no_skip_extracts_everything(self):
        with tempfile.TemporaryDirectory() as td:
            dest = self._extract(Path(td))
            self.assertTrue((dest / "BepInEx/plugins/ModA.dll").is_file())
            self.assertTrue((dest / "BepInEx/plugins/ModA.pdb").is_file())
            self.assertTrue((dest / "readme.txt").is_file())

    def test_skip_single_file_removes_it(self):
        with tempfile.TemporaryDirectory() as td:
            dest = self._extract(Path(td), skip_files={"BepInEx/plugins/ModA.dll"})
            self.assertFalse((dest / "BepInEx/plugins/ModA.dll").exists())
            self.assertTrue((dest / "BepInEx/plugins/ModA.pdb").is_file())
            self.assertTrue((dest / "readme.txt").is_file())

    def test_skip_multiple_files(self):
        with tempfile.TemporaryDirectory() as td:
            dest = self._extract(Path(td), skip_files={
                "BepInEx/plugins/ModA.dll", "readme.txt",
            })
            self.assertFalse((dest / "BepInEx/plugins/ModA.dll").exists())
            self.assertFalse((dest / "readme.txt").exists())
            self.assertTrue((dest / "BepInEx/plugins/ModA.pdb").is_file())

    def test_skip_nonexistent_entry_is_harmless(self):
        with tempfile.TemporaryDirectory() as td:
            dest = self._extract(Path(td), skip_files={"no/such/file.dll"})
            self.assertTrue((dest / "BepInEx/plugins/ModA.dll").is_file())
            self.assertTrue((dest / "readme.txt").is_file())

    def test_skip_empty_set_behaves_like_no_skip(self):
        with tempfile.TemporaryDirectory() as td:
            dest = self._extract(Path(td), skip_files=set())
            self.assertTrue((dest / "BepInEx/plugins/ModA.dll").is_file())
            self.assertTrue((dest / "readme.txt").is_file())


# ---------------------------------------------------------------------------
# _process_component  – end-to-end core_file logic
# ---------------------------------------------------------------------------

class ProcessComponentCoreFileTests(unittest.TestCase):
    """Test that _process_component builds skip_files from core_file
    depending on _core_selected."""

    def _run(self, core_selected: bool):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)

        zip_entries = {
            "BepInEx/plugins/ModA.dll": b"mod-a",
            "extra.txt": b"extra",
        }
        zpath = _make_zip(tmp, zip_entries)

        items = [
            {
                "id": "main", "name": "Core", "version": "1.0",
                "is_core": True, "required": True,
                "dependencies": [], "files": [],
            },
            {
                "id": "mod_a", "name": "Mod A", "version": "1.0",
                "required": False, "dependencies": ["main"],
                "files": [str(zpath)],
                "core_file": "BepInEx/plugins/ModA.dll",
                "actions": {str(zpath): str(tmp / "dest")},
            },
        ]
        meta = {
            "program_name": "Test", "version": "1.0", "author": "Test",
            "short_name": "Test", "need_admin": False, "has_uninstaller": False,
            "main_item": 0, "item_metadata": "items.json",
            "registry_key": "Test", "uninstall_registry_key": "Test",
            "footer_info": "", "license_file": "", "left_pic": "",
            "header_pic": "", "icon": "", "items": items,
        }
        with mock.patch.object(main, "get_metadata", return_value=meta), \
             mock.patch.object(main, "INSTALLER_METADATA", meta), \
             mock.patch.object(main, "get_installer_metadata", return_value=meta):
            thread = main.InstallThread(
                str(tmp / "dest"),
                {"main": core_selected, "mod_a": True},
            )
        recorder = mock.MagicMock()

        def _prepare_dir(path):
            os.makedirs(path, exist_ok=True)

        def _install_file(source, target):
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(target))

        recorder.prepare_directory.side_effect = _prepare_dir
        recorder.install_file.side_effect = _install_file
        thread.recorder = recorder
        thread._core_selected = core_selected
        thread.items_by_id = {i["id"]: i for i in items}

        dest = tmp / "dest"
        dest.mkdir(exist_ok=True)
        thread._process_component("mod_a")
        return dest

    def test_core_selected_core_file_is_extracted(self):
        dest = self._run(core_selected=True)
        self.assertTrue((dest / "BepInEx/plugins/ModA.dll").is_file())
        self.assertTrue((dest / "extra.txt").is_file())

    def test_core_not_selected_core_file_is_skipped(self):
        dest = self._run(core_selected=False)
        self.assertFalse((dest / "BepInEx/plugins/ModA.dll").exists())
        self.assertTrue((dest / "extra.txt").is_file())

    def test_no_core_field_extracts_regardless(self):
        """Component without core_file always extracts fully."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)

        zip_entries = {"file.dll": b"data"}
        zpath = _make_zip(tmp, zip_entries)
        items = [
            {
                "id": "main", "name": "Core", "version": "1.0",
                "is_core": True, "required": True,
                "dependencies": [], "files": [],
            },
            {
                "id": "mod_b", "name": "Mod B", "version": "1.0",
                "required": False, "dependencies": ["main"],
                "files": [str(zpath)],
                # no core_file
                "actions": {str(zpath): str(tmp / "dest")},
            },
        ]
        meta = {
            "program_name": "Test", "version": "1.0", "author": "Test",
            "short_name": "Test", "need_admin": False, "has_uninstaller": False,
            "main_item": 0, "item_metadata": "items.json",
            "registry_key": "Test", "uninstall_registry_key": "Test",
            "footer_info": "", "license_file": "", "left_pic": "",
            "header_pic": "", "icon": "", "items": items,
        }
        with mock.patch.object(main, "get_metadata", return_value=meta), \
             mock.patch.object(main, "INSTALLER_METADATA", meta), \
             mock.patch.object(main, "get_installer_metadata", return_value=meta):
            thread = main.InstallThread(
                str(tmp / "dest"),
                {"main": False, "mod_b": True},
            )
        recorder = mock.MagicMock()

        def _prepare_dir(path):
            os.makedirs(path, exist_ok=True)

        def _install_file(source, target):
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(target))

        recorder.prepare_directory.side_effect = _prepare_dir
        recorder.install_file.side_effect = _install_file
        thread.recorder = recorder
        thread._core_selected = False
        thread.items_by_id = {i["id"]: i for i in items}

        dest = tmp / "dest"
        dest.mkdir(exist_ok=True)
        thread._process_component("mod_b")
        # No core_file → nothing skipped
        self.assertTrue((dest / "file.dll").is_file())


if __name__ == "__main__":
    unittest.main()
