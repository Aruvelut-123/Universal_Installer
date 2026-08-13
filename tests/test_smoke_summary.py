import json
import tempfile
import unittest
from pathlib import Path

from scripts.render_smoke_summary import EXPECTED_REPORTS, render_reports


class SmokeSummaryTests(unittest.TestCase):
    def test_summary_lists_every_named_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _, artifact, filename in EXPECTED_REPORTS:
                (root / filename).write_text(json.dumps({
                    "artifact": artifact.lower(),
                    "checks": [
                        {
                            "check": "Qt application and event loop",
                            "status": "passed",
                            "detail": "PySide",
                        }
                    ],
                }), encoding="utf-8")
            markdown, failures = render_reports(root)

        self.assertEqual(failures, 0)
        self.assertEqual(markdown.count("Qt application and event loop"), 6)
        self.assertIn("| macOS x86_64 | Uninstaller |", markdown)

    def test_summary_marks_missing_reports_as_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            markdown, failures = render_reports(directory)

        self.assertEqual(failures, 6)
        self.assertEqual(markdown.count("No smoke report was uploaded"), 6)


if __name__ == "__main__":
    unittest.main()
