"""Installer behaviour around an existing (or broken) installation record.

A record kept in the game folder can be damaged, be moved together with the
folder, or be deleted by hand. None of those cases may stop the wizard, so
these tests pin the non-blocking fallback of the directory page and of the
component page that reads the record.

``main.py`` imports PySide at module level, so the Qt modules are stubbed. The
real :mod:`uninstaller` is used, because the record handling itself is what is
under test.
"""

import atexit
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import uninstaller

# ---------------------------------------------------------------------------
# main.py resolves metadata.json beside the application directory at import.
# ---------------------------------------------------------------------------

_APPLICATION_DIR = tempfile.mkdtemp(prefix="bbp_install_state_")
atexit.register(shutil.rmtree, _APPLICATION_DIR, True)

_ITEMS = [
    {
        "id": "core", "name": "Core", "version": "1.0",
        "required": True, "dependencies": [], "files": [],
    },
    {
        "id": "mod", "name": "Mod", "version": "2.0",
        "required": False, "dependencies": ["core"], "files": [],
    },
]
_METADATA = {
    "program_name": "Test", "short_name": "Test", "version": "1.0",
    "author": "Test", "need_admin": False, "has_uninstaller": False,
    "main_item": 0, "item_metadata": "items.json",
    "registry_key": "Test", "uninstall_registry_key": "Test",
    "footer_info": "", "license_file": "", "left_pic": "",
    "header_pic": "", "icon": "", "items": _ITEMS,
}
with open(
    os.path.join(_APPLICATION_DIR, "metadata.json"), "w", encoding="utf-8"
) as _file:
    json.dump(_METADATA, _file)
with open(os.path.join(_APPLICATION_DIR, "items.json"), "w", encoding="utf-8") as _file:
    json.dump({"items": _ITEMS}, _file)


class _FakeQThread:
    """Minimal QThread stand-in so InstallThread can be defined."""

    progress_updated = mock.MagicMock()
    finished = mock.MagicMock()

    def __init__(self, *args, **kwargs):
        pass


_QT_CORE = mock.MagicMock()
_QT_CORE.QThread = _FakeQThread
_QT_CORE.Qt = mock.MagicMock()


class _FakeWidget:
    """Base stand-in that keeps the page classes real Python classes."""

    def __init__(self, *args, **kwargs):
        pass


class _FakeMainWindow(_FakeWidget):
    pass


_QT_WIDGETS = mock.MagicMock()
_QT_WIDGETS.QWidget = _FakeWidget
_QT_WIDGETS.QMainWindow = _FakeMainWindow

_STUBS = {
    "PySide6": mock.MagicMock(),
    "PySide6.QtWidgets": _QT_WIDGETS,
    "PySide6.QtGui": mock.MagicMock(),
    "PySide6.QtCore": _QT_CORE,
    "PySide2": mock.MagicMock(),
    "PySide2.QtWidgets": _QT_WIDGETS,
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
        resolve_application_directory=lambda *a, **kw: Path(_APPLICATION_DIR),
    ),
}

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_WORKING_DIRECTORY = os.getcwd()
with mock.patch.dict(sys.modules, _STUBS):
    sys.modules.pop("main", None)
    import main  # noqa: E402
os.chdir(_WORKING_DIRECTORY)

# The Qt constants main.py compares against have to be real integers.
_QT = mock.MagicMock()
_QT.ItemIsEnabled = 1
_QT.ItemIsUserCheckable = 2
_QT.Checked = 2
_QT.Unchecked = 0
_QT.PartiallyChecked = 1
_QT.UserRole = 32
main.Qt = _QT


class _FakeTreeItem:
    """Tree item stand-in exposing only what the component page touches."""

    def __init__(self, enabled=True):
        self._enabled = enabled
        self.state = None
        self.label = ""

    def flags(self):
        return _QT.ItemIsEnabled if self._enabled else 0

    def setCheckState(self, column, state):
        self.state = state

    def checkState(self, column):
        return self.state

    def setText(self, column, text):
        self.label = text

    def text(self, column):
        return self.label


def _manifest_path(root):
    return root / main.INSTALL_DATA_DIRECTORY / main.INSTALL_MANIFEST_NAME


def _write_record(root, manifest):
    path = _manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(uninstaller._encode_manifest(manifest))
    return path


def _record(install_root, components=None):
    components = components or [
        {
            "id": "mod", "name": "Mod", "version": "2.0",
            "dependencies": ["core"], "required": False,
        },
    ]
    return {
        "schema_version": 2,
        "program_name": "Test",
        "install_root": str(install_root),
        "selected_components": [component["id"] for component in components],
        "components": components,
        "files": [],
    }


def _make_components_page():
    page = mock.MagicMock()
    page.loaded_install_root = None
    page.installation_notice = None
    page.installed_versions = {}
    page.items_by_id = {item["id"]: item for item in _ITEMS}
    page.tree_items_by_id = {item["id"]: _FakeTreeItem() for item in _ITEMS}
    page.base_labels_by_id = {item["id"]: item["name"] for item in _ITEMS}
    page.default_states_by_id = {
        "core": _QT.Checked, "mod": _QT.Unchecked,
    }
    return page


def _load_state(page, root):
    return main.ComponentsPage.load_installation_state(page, root)


class InstallerSelectionOptimizationTests(unittest.TestCase):
    def test_unique_component_files_deduplicate_shared_payloads(self):
        items = {
            "runtime": {"files": ["pack/shared.zip"]},
            "core": {"files": ["pack/shared.zip", "pack/core.zip"]},
        }

        self.assertEqual(
            list(main.iter_unique_component_files(items, ["runtime", "core"])),
            ["pack/shared.zip", "pack/core.zip"],
        )

    def test_component_file_list_deduplicates_repeated_entries(self):
        self.assertEqual(
            main.get_component_files({
                "files": ["pack/shared.zip", "pack/shared.zip"],
            }),
            ["pack/shared.zip"],
        )

    def test_incompatibility_is_symmetric_for_selection(self):
        items = {
            "core": {"incompatible": ["mod"]},
            "mod": {"incompatible": []},
        }

        self.assertEqual(
            main.incompatible_component_ids(items, "core"), {"mod"}
        )
        self.assertEqual(
            main.incompatible_component_ids(items, "mod"), {"core"}
        )

    def test_misspelled_imcompatible_field_is_normalized(self):
        items = [
            {
                "id": "core", "name": "Core", "required": True,
                "checked": True, "dependencies": [], "is_core": True,
                "imcompatible": ["alternative"], "files": [],
            },
            {
                "id": "alternative", "name": "Alternative", "required": False,
                "checked": False, "dependencies": [], "is_core": False,
                "files": [],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "items.json").write_text(
                json.dumps({"items": items}), encoding="utf-8"
            )
            with mock.patch.object(main, "APPLICATION_DIR", root), \
                 mock.patch.object(main, "METADATA_PATH", "items.json"), \
                 mock.patch.object(main, "metadata", None):
                normalized = main.get_metadata()

        self.assertEqual(
            normalized["items"][0]["incompatible"], ["alternative"]
        )

    def test_unknown_incompatible_component_is_rejected(self):
        items = [{
            "id": "core", "name": "Core", "required": True,
            "checked": True, "dependencies": [], "is_core": True,
            "incompatible": ["missing"], "files": [],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "items.json").write_text(
                json.dumps({"items": items}), encoding="utf-8"
            )
            with mock.patch.object(main, "APPLICATION_DIR", root), \
                 mock.patch.object(main, "METADATA_PATH", "items.json"), \
                 mock.patch.object(main, "metadata", None):
                with self.assertRaises(ValueError):
                    main.get_metadata()


class ComponentStateRecoveryTests(unittest.TestCase):
    def test_deleted_record_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = _make_components_page()

            installed, notice = _load_state(page, root)

            self.assertFalse(installed)
            self.assertIsNone(notice)
            self.assertEqual(page.installed_versions, {})
            self.assertEqual(
                page.tree_items_by_id["mod"].state, page.default_states_by_id["mod"]
            )

    def test_damaged_record_returns_a_notice_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = _manifest_path(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"UIM\x01damaged-payload")
            page = _make_components_page()

            installed, notice = _load_state(page, root)

            self.assertFalse(installed)
            self.assertIn("已损坏", notice)
            self.assertEqual(page.installed_versions, {})

    def test_relocated_record_keeps_installed_components(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            old_root = workspace / "old"
            old_root.mkdir()
            root = workspace / "new"
            root.mkdir()
            source = _write_record(old_root, _record(old_root))
            target = _manifest_path(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            page = _make_components_page()

            installed, notice = _load_state(page, root)

            self.assertTrue(installed)
            self.assertIn("不一致", notice)
            self.assertEqual(page.installed_versions, {"mod": "2.0"})
            self.assertEqual(page.tree_items_by_id["mod"].state, _QT.Checked)
            self.assertIn("已安装 v2.0", page.tree_items_by_id["mod"].label)

    def test_matching_record_restores_state_without_a_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_record(root, _record(root))
            page = _make_components_page()

            installed, notice = _load_state(page, root)

            self.assertTrue(installed)
            self.assertIsNone(notice)
            self.assertEqual(page.installed_versions, {"mod": "2.0"})

    def test_repeated_load_reuses_the_cached_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = _manifest_path(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"UIM\x01damaged-payload")
            page = _make_components_page()

            _load_state(page, root)
            installed, notice = _load_state(page, root)

            self.assertFalse(installed)
            self.assertIn("已损坏", notice)

    def test_unexpected_failure_still_returns_a_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = _make_components_page()
            with mock.patch.object(
                main, "load_existing_installation", side_effect=TypeError("boom")
            ):
                installed, notice = _load_state(page, root)

            self.assertFalse(installed)
            self.assertIn("无法读取", notice)
            self.assertEqual(page.installed_versions, {})


class DirectoryPageContinuationTests(unittest.TestCase):
    """The reported bug: the wizard stopped right after the warning dialog."""

    def _make_directory_page(self, root):
        components = _make_components_page()
        components.load_installation_state = (
            lambda install_root: _load_state(components, install_root)
        )
        page = mock.MagicMock()
        page.path_input.text.return_value = str(root)
        page.parent.pages = {"components": components}
        return page

    def _require_ascii_path(self, root):
        if any(ord(character) > 127 for character in str(root)):
            self.skipTest("安装路径校验测试需要 ASCII 临时目录")

    def test_wizard_continues_after_a_damaged_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._require_ascii_path(root)
            path = _manifest_path(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"UIM\x01damaged-payload")
            page = self._make_directory_page(root)
            with mock.patch.object(main, "QMessageBox") as message_box:
                main.DirectoryPage.on_next(page)

            message_box.information.assert_called_once()
            self.assertIn("已损坏", message_box.information.call_args[0][2])
            self.assertEqual(
                [call[0] for call in message_box.method_calls], ["information"]
            )
            page.parent.go_to_page.assert_called_once_with("components")
            self.assertEqual(page.parent.install_path, str(root.resolve()))

    def test_wizard_continues_after_a_relocated_record(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self._require_ascii_path(workspace)
            old_root = workspace / "old"
            old_root.mkdir()
            root = workspace / "new"
            root.mkdir()
            source = _write_record(old_root, _record(old_root))
            target = _manifest_path(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            page = self._make_directory_page(root)
            with mock.patch.object(main, "QMessageBox") as message_box:
                main.DirectoryPage.on_next(page)

            message_box.information.assert_called_once()
            self.assertIn("不一致", message_box.information.call_args[0][2])
            page.parent.go_to_page.assert_called_once_with("components")

    def test_wizard_continues_with_a_valid_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._require_ascii_path(root)
            _write_record(root, _record(root))
            page = self._make_directory_page(root)
            with mock.patch.object(main, "QMessageBox") as message_box:
                main.DirectoryPage.on_next(page)

            message_box.information.assert_called_once()
            self.assertIn("现有安装", message_box.information.call_args[0][1])
            page.parent.go_to_page.assert_called_once_with("components")


if __name__ == "__main__":
    unittest.main()
