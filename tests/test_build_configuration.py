import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BuildConfigurationTests(unittest.TestCase):
    def test_dependabot_resolves_for_python_38(self):
        python_version = (ROOT / ".python-version").read_text(
            encoding="utf-8"
        ).strip()
        self.assertEqual(python_version.split(".")[:2], ["3", "8"])

        for relative_path in (
            ".github/workflows/build-app.yml",
            ".github/workflows/build-release.yml",
        ):
            workflow = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn('python-version: "3.8.10"', workflow)
            self.assertIn('python-version: "3.8.18"', workflow)

    def test_release_architecture_matrix_and_installer_names(self):
        for relative_path in (
            ".github/workflows/build-app.yml",
            ".github/workflows/build-release.yml",
        ):
            workflow = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn('architecture: x86', workflow)
            self.assertIn('--platform linux/386', workflow)
            self.assertIn('i386/debian:bullseye', workflow)
            self.assertIn('dist/main.exe', workflow)
            self.assertIn('main.bin', workflow)
            self.assertIn('main.AppImage', workflow)
            self.assertIn('macos.zip', workflow)
            self.assertNotIn('main-windows-x86.exe', workflow)
            self.assertNotIn('uninstall-linux-x64', workflow)

    def test_linux_build_verifies_i686_and_uses_ccache(self):
        script = (ROOT / "scripts/build_linux_x86.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('ELF 32-bit.*Intel 80386', script)
        self.assertIn('/usr/lib/ccache', script)
        self.assertIn('ccache --show-stats', script)
        self.assertIn('appimagetool-i686.AppImage', script)

        for app_run in (
            "scripts/linux-main-apprun",
            "scripts/linux-uninstaller-apprun",
        ):
            launcher = (ROOT / app_run).read_text(encoding="utf-8")
            self.assertNotIn("QT_SCALE_FACTOR", launcher)
            self.assertNotIn("QT_AUTO_SCREEN_SCALE_FACTOR", launcher)

    def test_x64_linux_gets_x86_uninstaller_but_x64_runtime(self):
        items = json.loads(
            (ROOT / "pack/items_example.json").read_text(encoding="utf-8")
        )["components"]
        runtime = next(item for item in items if item["component_id"] == "runtime")
        core = next(item for item in items if item["component_id"] == "core")

        self.assertEqual(runtime["linux_x86_files"], ["pack/runtime-linux-x86.zip"])
        self.assertEqual(runtime["linux_x64_files"], ["pack/runtime-linux-x64.zip"])
        self.assertEqual(core["linux_x86_files"], core["linux_x64_files"])


if __name__ == "__main__":
    unittest.main()
