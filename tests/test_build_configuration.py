import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BuildConfigurationTests(unittest.TestCase):
    def test_packaging_build_uses_an_input_allowlist(self):
        workflow = (ROOT / ".github/workflows/build-app.yml").read_text(
            encoding="utf-8"
        )
        trigger_section = workflow.split("concurrency:", 1)[0]

        self.assertEqual(trigger_section.count("    paths:\n"), 2)
        self.assertNotIn("paths-ignore:", trigger_section)
        for build_input in (
            "'*.py'",
            "'requirements*.txt'",
            "'pack/icon.ico'",
            "'scripts/**'",
            "'.github/actions/**'",
            "'.github/workflows/build-app.yml'",
            "'.github/workflows/build-release.yml'",
        ):
            self.assertIn(build_input, trigger_section)

    def test_dependabot_only_updates_github_actions(self):
        dependabot = (ROOT / ".github/dependabot.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("package-ecosystem: github-actions", dependabot)
        self.assertNotIn("package-ecosystem: pip", dependabot)

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
            self.assertIn('macos.zip', workflow)
            self.assertNotIn('main-windows-x86.exe', workflow)
            self.assertNotIn('uninstall-linux-x64', workflow)
            self.assertNotIn('AppImage', workflow)
            self.assertNotIn('nuitka', workflow.lower())

    def test_linux_build_uses_pyinstaller_and_smoke_tests_i686(self):
        script = (ROOT / "scripts/build_linux_x86.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('ELF 32-bit.*Intel 80386', script)
        self.assertEqual(
            script.count('python3 scripts/run_linux_pyinstaller.py'), 2
        )
        launcher = (ROOT / "scripts/run_linux_pyinstaller.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('compat.PY3_BASE_MODULES.add("ipaddress")', launcher)
        self.assertEqual(script.count('smoke_test ./'), 2)
        self.assertIn('QT_QPA_PLATFORM=offscreen', script)
        self.assertIn('UNIVERSAL_INSTALLER_SMOKE_TEST=1', script)
        for entrypoint in ("main.py", "uninstaller.py"):
            source = (ROOT / entrypoint).read_text(encoding="utf-8")
            self.assertIn('UNIVERSAL_INSTALLER_SMOKE_TEST', source)
            self.assertIn('def run_smoke_test(', source)
        self.assertNotIn('AppImage', script)
        self.assertNotIn('nuitka', script.lower())

    def test_packaging_builds_persist_pip_and_pyinstaller_caches(self):
        linux_script = (ROOT / "scripts/build_linux_x86.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("PIP_CACHE_DIR", linux_script)
        self.assertIn("PIP_WHEEL_DIR", linux_script)
        self.assertIn("pip wheel", linux_script)
        self.assertIn("--no-index", linux_script)

        for relative_path in (
            ".github/workflows/build-app.yml",
            ".github/workflows/build-release.yml",
        ):
            workflow = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertEqual(workflow.count("Restore i686 pip cache"), 2)
            self.assertEqual(workflow.count("PIP_CACHE_DIR=/pip-cache"), 2)
            self.assertEqual(workflow.count("Restore i686 PyInstaller cache"), 2)
            self.assertEqual(workflow.count("Restore macOS PyInstaller cache"), 2)
            self.assertEqual(workflow.count(".pyinstaller-work-linux-x86"), 6)
            self.assertEqual(workflow.count(".pyinstaller-work-macos-x64"), 4)
            self.assertNotIn("ccache", workflow.lower())

    def test_windows_builds_reuse_pyinstaller_cache(self):
        cache_action = (
            ROOT / ".github/actions/setup-windows-pyinstaller-cache/action.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("PYINSTALLER_CONFIG_DIR", cache_action)
        self.assertIn("PYINSTALLER_WORKPATH", cache_action)
        self.assertIn(".pyinstaller-work-windows-x86", cache_action)
        self.assertIn("actions/cache@v6", cache_action)

        for relative_path in (
            ".github/workflows/build-app.yml",
            ".github/workflows/build-release.yml",
        ):
            workflow = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertEqual(
                workflow.count("setup-windows-pyinstaller-cache"), 2
            )
            self.assertEqual(
                workflow.count('--workpath "$env:PYINSTALLER_WORKPATH"'), 2
            )
            self.assertNotIn("--clean", workflow)

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
