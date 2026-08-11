import tempfile
import unittest
from pathlib import Path
from unittest import mock

import uninstaller


class ComponentUninstallTests(unittest.TestCase):
    def test_installed_component_versions_supports_versionless_components(self):
        manifest = {
            "components": [
                {"id": "core", "version": "1.2.3"},
                {"id": "extras", "version": None},
            ]
        }

        self.assertEqual(
            uninstaller.installed_component_versions(manifest),
            {"core": "1.2.3", "extras": None},
        )

    def make_installation(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        data = root / uninstaller.INSTALL_DATA_DIRECTORY
        manifest_path = data / uninstaller.INSTALL_MANIFEST_NAME
        for name, contents in (
            ("bbpc.dll", b"core"),
            ("BepInEx/core/runtime.dll", b"runtime"),
            ("BepInEx/plugins/mod.dll", b"mod"),
            ("shared.dll", b"shared"),
            ("uninstall.AppImage", b"uninstaller"),
        ):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        components = [
            {
                "id": "runtime", "name": "BepInEx", "version": "5.4.23.5",
                "dependencies": [], "required": True,
            },
            {
                "id": "core", "name": "BBPC", "version": "1.18.4",
                "dependencies": ["runtime"], "required": True,
                "remove_directories_on_uninstall": [
                    "{install_path}/BBPC-generated"
                ],
            },
            {
                "id": "api", "name": "Dev API", "version": "11.1.0.2",
                "dependencies": ["runtime"], "required": True,
            },
            {
                "id": "mod", "name": "Mod", "version": "1.0.0",
                "dependencies": ["api"], "required": False,
            },
        ]
        manifest = {
            "schema_version": 2,
            "program_name": "Test",
            "install_root": str(root),
            "selected_components": [item["id"] for item in components],
            "components": components,
            "core_component": "core",
            "files": [
                {"path": "bbpc.dll", "backup": None, "components": ["core"]},
                {
                    "path": "BepInEx/core/runtime.dll", "backup": None,
                    "components": ["runtime"],
                },
                {
                    "path": "BepInEx/plugins/mod.dll", "backup": None,
                    "components": ["mod"],
                },
                {
                    "path": "shared.dll", "backup": None,
                    "components": ["core", "api"],
                },
                {
                    "path": "uninstall.AppImage", "backup": None,
                    "components": ["core"],
                },
            ],
            "created_directories": ["BepInEx", "BepInEx/core", "BepInEx/plugins"],
            "windows_registry": {
                "hive": "HKCU", "product_key": "Software\\Test",
                "uninstall_key": "Software\\Uninstall\\Test",
            },
        }
        uninstaller._atomic_write_manifest(manifest_path, manifest)
        generated = root / "BBPC-generated"
        generated.mkdir()
        (generated / "untracked.cache").write_bytes(b"generated")
        return temporary, root, manifest_path, manifest

    def test_dependency_selection_includes_transitive_dependents(self):
        temporary, _, _, manifest = self.make_installation()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(
            uninstaller.dependent_removal_closure(manifest, {"api"}),
            {"api", "mod"},
        )
        self.assertEqual(
            uninstaller.dependent_removal_closure(manifest, {"core"}),
            {"core"},
        )

    def test_core_uninstall_keeps_runtime_mods_and_removes_registry(self):
        temporary, root, manifest_path, manifest = self.make_installation()
        self.addCleanup(temporary.cleanup)
        running_uninstaller = root / "uninstall.AppImage"
        with mock.patch.object(
            uninstaller, "remove_windows_uninstall_entry"
        ) as remove, mock.patch.object(
                uninstaller,
                "_current_uninstaller_container",
                return_value=running_uninstaller,
        ):
            errors, deferred = uninstaller.uninstall(manifest_path, manifest, {"core"})
        self.assertEqual(errors, [])
        self.assertEqual(deferred, running_uninstaller)
        self.assertFalse((root / "bbpc.dll").exists())
        self.assertFalse((root / "BBPC-generated").exists())
        self.assertTrue((root / "BepInEx/core/runtime.dll").is_file())
        self.assertTrue((root / "BepInEx/plugins/mod.dll").is_file())
        self.assertTrue((root / "shared.dll").is_file())
        remove.assert_called_once_with(manifest["windows_registry"])

        _, updated = uninstaller.load_manifest(manifest_path)
        self.assertNotIn("core", updated["selected_components"])
        self.assertIsNone(updated["windows_registry"])
        shared = next(entry for entry in updated["files"] if entry["path"] == "shared.dll")
        self.assertEqual(shared["components"], ["api"])
        self.assertNotIn(
            "uninstall.AppImage", {entry["path"] for entry in updated["files"]}
        )

    def test_partial_uninstall_keeps_registry_when_core_remains(self):
        temporary, root, manifest_path, manifest = self.make_installation()
        self.addCleanup(temporary.cleanup)
        with mock.patch.object(uninstaller, "remove_windows_uninstall_entry") as remove:
            errors, _ = uninstaller.uninstall(manifest_path, manifest, {"mod"})
        self.assertEqual(errors, [])
        self.assertFalse((root / "BepInEx/plugins/mod.dll").exists())
        self.assertTrue((root / "bbpc.dll").is_file())
        remove.assert_not_called()
        _, updated = uninstaller.load_manifest(manifest_path)
        self.assertEqual(updated["windows_registry"], manifest["windows_registry"])

    def test_partial_uninstall_removes_only_directories_left_empty(self):
        temporary, root, manifest_path, manifest = self.make_installation()
        self.addCleanup(temporary.cleanup)
        removable = root / "Mods" / "Core" / "cache" / "generated.txt"
        removable.parent.mkdir(parents=True)
        removable.write_bytes(b"generated")
        retained = root / "Mods" / "keep-user-file.txt"
        retained.write_bytes(b"user")
        manifest["files"].append({
            "path": "Mods/Core/cache/generated.txt",
            "backup": None,
            "components": ["core"],
        })
        manifest["created_directories"] = [
            "Mods", "Mods/Core", "Mods/Core/cache"
        ]

        errors, _ = uninstaller.uninstall(
            manifest_path, manifest, {"core"}
        )

        self.assertEqual(errors, [])
        self.assertFalse((root / "Mods" / "Core").exists())
        self.assertTrue(retained.is_file())
        self.assertTrue((root / "Mods").is_dir())

    def test_configured_uninstall_directories_cannot_escape_install_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "install"
            root.mkdir()
            with self.assertRaises(ValueError):
                uninstaller._resolve_uninstall_directory(root, "../outside")
            with self.assertRaises(ValueError):
                uninstaller._resolve_uninstall_directory(root, "{install_path}")


class ManifestRecordingTests(unittest.TestCase):
    def test_recorder_tracks_component_versions_and_file_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = uninstaller.InstallRecorder(
                root,
                {"program_name": "Test", "version": "2", "author": "Author"},
                [
                    {
                        "id": "runtime", "name": "Runtime", "version": "5.4.23.5",
                        "dependencies": [], "required": True,
                    },
                    {
                        "id": "core", "name": "Core", "version": "1.18.4",
                        "dependencies": ["runtime"], "required": True,
                    },
                ],
                {},
                core_component="core",
            )
            recorder.begin_component("core")
            target = root / "core.dll"
            recorder.prepare_file(target)
            target.write_bytes(b"installed")
            recorder.finalize()
            _, manifest = uninstaller.load_manifest(recorder.manifest_path)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["core_component"], "core")
            versions = {item["id"]: item["version"] for item in manifest["components"]}
            self.assertEqual(versions["runtime"], "5.4.23.5")
            self.assertEqual(manifest["files"][0]["components"], ["core"])

    def test_update_skips_identical_files_and_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "install"
            root.mkdir()
            source = workspace / "payload.dll"
            source.write_bytes(b"same payload")
            component_v1 = {
                "id": "mod", "name": "Mod", "version": "1.0",
                "dependencies": [], "required": False,
            }
            metadata = {
                "program_name": "Test", "version": "1", "author": "Author"
            }

            recorder = uninstaller.InstallRecorder(
                root, metadata, [component_v1], {}, core_component="mod"
            )
            recorder.begin_component("mod")
            target = root / "payload.dll"
            self.assertTrue(recorder.install_file(source, target))
            stale = root / "old.dll"
            recorder.install_file(source, stale)
            recorder.finish_component("mod")
            recorder.finalize()

            original_mtime = target.stat().st_mtime_ns
            component_v2 = dict(component_v1, version="2.0")
            recorder = uninstaller.InstallRecorder(
                root, metadata, [component_v2], {}, core_component="mod"
            )
            recorder.begin_component("mod")
            self.assertFalse(recorder.install_file(source, target))
            recorder.finish_component("mod")
            recorder.finalize()

            self.assertEqual(target.stat().st_mtime_ns, original_mtime)
            self.assertFalse(stale.exists())
            self.assertEqual(recorder.skipped_files, 1)
            _, manifest = uninstaller.load_manifest(recorder.manifest_path)
            self.assertEqual(manifest["components"][0]["version"], "2.0")
            self.assertEqual(manifest["files"][0]["sha256"], uninstaller._file_digest(source))


if __name__ == "__main__":
    unittest.main()
