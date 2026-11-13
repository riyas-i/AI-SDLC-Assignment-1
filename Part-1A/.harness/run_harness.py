"""Quality-gate harness for the Smart Todo CLI (constitution I, II, III, VI, VII).

Usage (PowerShell, from Part-1A with .venv active):

    python .harness\\run_harness.py [--label NAME]

Runs, in order, and saves each step's combined output to ``evidence/<label>/<step>.txt``:

1. ruff          ``ruff check .``                                  (0 errors)
2. bandit        ``bandit -r src -ll``                             (0 Medium/High issues)
3. pytest        ``pytest --cov=src ... --cov-fail-under=85``      (all pass, >= 85 % lines)
4. traceability  every ``AC-NNN`` in spec.md has a ``test_acNNN_*`` test

Then writes ``summary.json`` and ``summary.md`` and prints ``OVERALL: PASS|FAIL``. Exits 0 only
if every step passed. Standard library only; subprocesses use list arguments, never a shell.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET  # parses only coverage/junit XML this harness just wrote
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "specs" / "001-smart-todo-cli" / "spec.md"
TESTS_DIR = ROOT / "tests"
COVERAGE_MIN = 85
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

AC_IN_SPEC_RE = re.compile(r"\bAC-(\d{3})\b")
TEST_DEF_RE = re.compile(r"^\s*def (test_ac\d{3}\w*)\s*\(", re.MULTILINE)
TEST_AC_PREFIX_RE = re.compile(r"^test_((?:ac\d{3}_?)+)")
AC_TOKEN_RE = re.compile(r"ac(\d{3})")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all quality gates and write evidence.")
    parser.add_argument(
        "--label",
        default="latest",
        help="evidence sub-folder name (default: latest), e.g. red-baseline or final",
    )
    args = parser.parse_args(argv)
    if not LABEL_RE.match(args.label):
        parser.error("--label may contain only letters, digits, '.', '_' and '-'")
    return args


def run_tool(name: str, args: list[str], out_dir: Path) -> int:
    """Run ``python -m <args>`` in ROOT, save combined output to ``<name>.txt``."""
    cmd = [sys.executable, "-m", *args]
    proc = subprocess.run(  # list args, shell=False, fixed tool names
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    shown = " ".join(["python", "-m", *args])
    text = f"$ {shown}\n(exit code {proc.returncode})\n\n{proc.stdout}"
    if proc.stderr:
        text += f"\n--- stderr ---\n{proc.stderr}"
    (out_dir / f"{name}.txt").write_text(text, encoding="utf-8")
    return proc.returncode


def tool_version(args: list[str]) -> str:
    proc = subprocess.run(  # list args, shell=False
        [sys.executable, "-m", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    lines = (proc.stdout or proc.stderr).strip().splitlines()
    if not lines:
        return "unknown"
    # `python -m bandit --version` reports its program name as "__main__.py".
    return lines[0].strip().replace("__main__.py", args[0], 1)


def traceability(out_dir: Path) -> tuple[int, int, int]:
    """Map every AC in spec.md to the tests named after it.

    Returns ``(exit_code, traced, total)``. Fails if any AC has no test, or a test names an AC
    that does not exist in the spec.
    """
    spec_acs = sorted(set(AC_IN_SPEC_RE.findall(SPEC.read_text(encoding="utf-8"))))
    tests_by_ac: dict[str, list[str]] = {}
    for test_file in sorted(TESTS_DIR.glob("*.py")):
        for name in TEST_DEF_RE.findall(test_file.read_text(encoding="utf-8")):
            prefix = TEST_AC_PREFIX_RE.match(name)
            if prefix is None:
                continue
            for ac in AC_TOKEN_RE.findall(prefix.group(1)):
                entry = f"{test_file.name}::{name}"
                if entry not in tests_by_ac.setdefault(ac, []):
                    tests_by_ac[ac].append(entry)

    missing = [ac for ac in spec_acs if ac not in tests_by_ac]
    orphans = sorted(ac for ac in tests_by_ac if ac not in spec_acs)
    traced = len(spec_acs) - len(missing)

    lines = [
        f"Spec: {SPEC.relative_to(ROOT).as_posix()}",
        f"Tests: {TESTS_DIR.relative_to(ROOT).as_posix()}/*.py",
        "",
    ]
    for ac in spec_acs:
        tests = tests_by_ac.get(ac)
        if tests:
            lines.append(f"AC-{ac}: {len(tests)} test(s)")
            lines.extend(f"    {t}" for t in tests)
        else:
            lines.append(f"AC-{ac}: MISSING (no test_ac{ac}_* test)")
    lines.append("")
    if orphans:
        lines.append("Tests naming ACs that are not in spec.md:")
        for ac in orphans:
            lines.extend(f"    AC-{ac}: {t}" for t in tests_by_ac[ac])
        lines.append("")
    lines.append(f"{traced}/{len(spec_acs)} ACs traced")
    passed = not missing and not orphans and bool(spec_acs)
    lines.append("RESULT: " + ("PASS" if passed else "FAIL"))
    (out_dir / "traceability.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (0 if passed else 1), traced, len(spec_acs)


def coverage_percent(xml_path: Path) -> float | None:
    if not xml_path.is_file():
        return None
    try:
        rate = ET.parse(xml_path).getroot().get("line-rate")  # trusted: written by this run
        return round(float(rate) * 100, 2) if rate is not None else None
    except (ET.ParseError, ValueError):
        return None


def junit_counts(xml_path: Path) -> dict[str, int] | None:
    if not xml_path.is_file():
        return None
    try:
        root = ET.parse(xml_path).getroot()  # trusted: written by this run
    except ET.ParseError:
        return None
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return totals


def write_summary_md(summary: dict, out_dir: Path) -> None:
    rows = [
        f"# Harness summary: `{summary['label']}`",
        "",
        f"- Timestamp (UTC): {summary['timestamp']}",
        f"- Python: {summary['python_version']} ({summary['platform']})",
        "- Tools: " + ", ".join(f"{k} `{v}`" for k, v in summary["tool_versions"].items()),
        "",
        "| Step | Exit code | Result |",
        "|------|-----------|--------|",
    ]
    for name, step in summary["steps"].items():
        rows.append(f"| {name} | {step['exit_code']} | {'PASS' if step['passed'] else 'FAIL'} |")
    cov = summary["coverage_percent"]
    tests = summary["tests"]
    rows += [
        "",
        f"- Coverage: {'n/a' if cov is None else f'{cov:.2f} %'} (minimum {COVERAGE_MIN} %)",
        f"- ACs traced: {summary['acs_traced']}/{summary['acs_total']}",
    ]
    if tests is not None:
        rows.append(
            f"- Tests: {tests['tests']} total, {tests['passed']} passed, "
            f"{tests['failures']} failed, {tests['errors']} errors, {tests['skipped']} skipped"
        )
    rows += ["", f"**OVERALL: {summary['overall'].upper()}**", ""]
    (out_dir / "summary.md").write_text("\n".join(rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = ROOT / "evidence" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    rel_out = out_dir.relative_to(ROOT).as_posix()
    coverage_xml = out_dir / "coverage.xml"
    junit_xml = out_dir / "junit.xml"
    for stale in (coverage_xml, junit_xml):
        stale.unlink(missing_ok=True)

    steps: dict[str, dict[str, object]] = {}

    def record(name: str, code: int) -> None:
        steps[name] = {"exit_code": code, "passed": code == 0}
        print(f"[{'PASS' if code == 0 else 'FAIL'}] {name} (exit {code})", flush=True)

    record("ruff", run_tool("ruff", ["ruff", "check", "."], out_dir))
    record("bandit", run_tool("bandit", ["bandit", "-r", "src", "-ll"], out_dir))
    record(
        "pytest",
        run_tool(
            "pytest",
            [
                "pytest",
                "--cov=src",
                "--cov-report=term-missing",
                f"--cov-report=xml:{rel_out}/coverage.xml",
                f"--cov-fail-under={COVERAGE_MIN}",
                f"--junitxml={rel_out}/junit.xml",
            ],
            out_dir,
        ),
    )
    trace_code, traced, total = traceability(out_dir)
    record("traceability", trace_code)

    overall = all(step["passed"] for step in steps.values())
    summary = {
        "label": args.label,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "tool_versions": {
            "ruff": tool_version(["ruff", "--version"]),
            "bandit": tool_version(["bandit", "--version"]),
            "pytest": tool_version(["pytest", "--version"]),
        },
        "steps": steps,
        "coverage_percent": coverage_percent(coverage_xml),
        "coverage_minimum": COVERAGE_MIN,
        "tests": junit_counts(junit_xml),
        "acs_traced": traced,
        "acs_total": total,
        "overall": "pass" if overall else "fail",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_summary_md(summary, out_dir)

    print(f"Evidence written to {rel_out}/")
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
