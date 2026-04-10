"""Parse JUnit XML test results and output markdown table to GitHub Actions step summary."""

import sys
import xml.etree.ElementTree as ET


def main():
    if len(sys.argv) < 2:
        print("Usage: python format_results.py <junit-xml-path>", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(sys.argv[1])
    root = tree.getroot()

    passed = []
    failed = []
    errors = []

    for suite in root.iter("testsuite"):
        for case in suite.iter("testcase"):
            name = case.attrib.get("classname", "") + "::" + case.attrib.get("name", "")
            time_s = case.attrib.get("time", "0")

            failure = case.find("failure")
            error = case.find("error")

            if failure is not None:
                msg = failure.attrib.get("message", "").replace("\n", " ")
                failed.append((name, time_s, msg))
            elif error is not None:
                msg = error.attrib.get("message", "").replace("\n", " ")
                errors.append((name, time_s, msg))
            else:
                passed.append((name, time_s))

    # Markdown table for GITHUB_STEP_SUMMARY
    total = len(passed) + len(failed) + len(errors)
    summary_lines = []
    summary_lines.append("### Test Results")
    summary_lines.append("")
    summary_lines.append(f"**{len(passed)}** passed, **{len(failed)}** failed, **{len(errors)}** errors - **{total}** total")
    summary_lines.append("")
    summary_lines.append("| Status | Test | Time |")
    summary_lines.append("|--------|------|------|")

    for name, time_s, msg in failed:
        summary_lines.append(f"| :x: FAIL | `{name}` | {time_s}s |")
    for name, time_s, msg in errors:
        summary_lines.append(f"| :x: ERROR | `{name}` | {time_s}s |")
    for name, time_s in passed:
        summary_lines.append(f"| :white_check_mark: PASS | `{name}` | {time_s}s |")

    summary = "\n".join(summary_lines)

    # Write to GITHUB_STEP_SUMMARY if available
    import os
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(summary + "\n")
    else:
        # Print to stdout if not in CI
        print(summary)


if __name__ == "__main__":
    main()
