"""Render packaged-binary smoke reports as a GitHub Actions table."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


EXPECTED_REPORTS = (
    ("Windows x86", "Installer", "smoke-report-windows-installer.json"),
    ("Windows x86", "Uninstaller", "smoke-report-windows-uninstaller.json"),
    ("Linux i686", "Installer", "smoke-report-linux-installer.json"),
    ("Linux i686", "Uninstaller", "smoke-report-linux-uninstaller.json"),
    ("macOS x86_64", "Installer", "smoke-report-macos-installer.json"),
    ("macOS x86_64", "Uninstaller", "smoke-report-macos-uninstaller.json"),
)


def escape_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_reports(directory):
    directory = Path(directory)
    rows = []
    failures = 0
    for platform_name, artifact_name, filename in EXPECTED_REPORTS:
        path = directory / filename
        if not path.is_file():
            rows.append((
                platform_name, artifact_name, "Report generated",
                "❌ Failed", "No smoke report was uploaded",
            ))
            failures += 1
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            checks = report["checks"]
            if not isinstance(checks, list) or not checks:
                raise ValueError("checks must be a non-empty list")
            for check in checks:
                passed = check.get("status") == "passed"
                rows.append((
                    platform_name,
                    artifact_name,
                    check.get("check", "Unnamed check"),
                    "✅ Passed" if passed else "❌ Failed",
                    check.get("detail", ""),
                ))
                failures += not passed
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            rows.append((
                platform_name, artifact_name, "Report parsed",
                "❌ Failed", "{}: {}".format(type(error).__name__, error),
            ))
            failures += 1

    lines = [
        "## Packaged binary functional smoke tests",
        "",
        "| Platform | Artifact | Check | Result | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        "| {} | {} | {} | {} | {} |".format(
            *(escape_cell(value) for value in row)
        )
        for row in rows
    )
    lines.extend(("", "**{} checks failed.**".format(failures)))
    return "\n".join(lines) + "\n", failures


def main():
    report_directory = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    markdown, failures = render_reports(report_directory)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(markdown)
    else:
        print(markdown, end="")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
