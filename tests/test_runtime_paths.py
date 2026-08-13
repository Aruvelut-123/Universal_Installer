import tempfile
import unittest
from pathlib import Path

from platform_utils import resolve_application_directory


class RuntimePathTests(unittest.TestCase):
    def test_script_uses_source_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "src" / "main.py"
            source.parent.mkdir()

            result = resolve_application_directory(
                source, frozen=False, environment={}
            )

            self.assertEqual(result, source.parent.resolve())

    def test_frozen_macos_binary_resolves_outside_app_bundle(self):
        executable = Path("/Applications/Test.app/Contents/MacOS/main")

        result = resolve_application_directory(
            "unused.py", frozen=True, environment={}, executable=executable
        )

        self.assertEqual(result, Path("/Applications"))

if __name__ == "__main__":
    unittest.main()
