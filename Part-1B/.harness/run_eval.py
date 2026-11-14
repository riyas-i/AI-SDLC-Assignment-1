"""Evaluation runner (T025; FR-104 - FR-106, AC-079, SC-007, SC-008, contracts/cli.md).

    python .harness/run_eval.py [--dataset evals/dataset.json] [--label NAME] [--limit N]
                                [--out evidence] [--compare-with LABEL]

Writes evidence/eval-runs/<label>/results.json and summary.md (never overwritten; an existing
label is refused) and copies results.json to evidence/eval-results.json.
Exit codes: 0 PASS, 1 FAIL (or label exists), 2 INCONCLUSIVE, 3 INCOMPLETE / setup error.

Results are built from an explicit allow-list of configuration fields; no environment value
(in particular GEMINI_API_KEY) is ever written (FR-085, research R3).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import sys
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from expense.llm_client import ModelError

import invariant_check
import outcome_check
import quality_check
import schema_check
import verdict
from expense import config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "dataset.json"
DEFAULT_OUT = ROOT / "evidence"
EXIT_CODES = {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2, "INCOMPLETE": 3}
EXIT_LABEL_EXISTS = 1
EXIT_SETUP_ERROR = 3
SC007_MIN_RATE = 0.95
SC008_MAX_P95_MS = 15000
CHECKERS = (schema_check, invariant_check, outcome_check, quality_check)
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class LabelExistsError(Exception):
    """The run folder already exists; earlier evidence is never overwritten (FR-106)."""


# --------------------------------------------------------------------------- helpers


def exit_code_for(verdict_value: str) -> int:
    return EXIT_CODES[verdict_value]


def run_config() -> dict:
    """Allow-listed configuration only (AC-079, FR-085)."""
    return {
        "model": config.MODEL_NAME,
        "temperature": config.TEMPERATURE,
        "call_delay_seconds": config.CALL_DELAY_SECONDS,
        "timeout_seconds": config.TIMEOUT_SECONDS,
        "retry_policy": {
            "max_attempts": len(config.RETRY_BACKOFF_SECONDS) + 1,
            "backoff_seconds": list(config.RETRY_BACKOFF_SECONDS),
            "retried": ["timeout", "network", "quota", "server"],
            "not_retried": ["api_error", "invalid_response"],
        },
        "sdk": f"google-genai {importlib.metadata.version('google-genai')}",
        "python": platform.python_version(),
    }


def _attempt_dict(attempt) -> dict:
    if dataclasses.is_dataclass(attempt):
        return dataclasses.asdict(attempt)
    return dict(attempt)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def evaluate_case(case: dict, assess_fn: Callable, client) -> dict:
    """Run one case and its four checks. ModelError → `model_error`, excluded from scoring."""
    error_type = None
    error_text = None
    output = None
    start = time.perf_counter()
    try:
        output = assess_fn(case["input"], date.fromisoformat(case["today"]), client)
        attempts = list(getattr(client, "last_attempts", None) or [])
    except ModelError as exc:
        error_type = exc.error_type
        attempts = list(exc.attempts or [])
    except Exception as exc:  # internal/usage errors are case failures, not model errors
        error_text = type(exc).__name__
        attempts = list(getattr(client, "last_attempts", None) or [])
    elapsed_ms = round((time.perf_counter() - start) * 1000)

    if error_type is not None:
        checks = []
        status = "model_error"
    else:
        checks = [checker.check(case, output) for checker in CHECKERS]
        status = "pass" if verdict.case_passed(checks) else "fail"

    return {
        "id": case["id"],
        "tags": list(case["tags"]),
        "kind": case.get("kind"),
        "status": status,
        "output": output,
        "checks": [c.to_dict() for c in checks],
        "model_error": error_type,
        "error": error_text,
        "attempts": [_attempt_dict(a) for a in attempts],
        "elapsed_ms": elapsed_ms,
    }


def compute_latency(case_results: list[dict]) -> dict:
    """SC-008: nearest-rank p50/p95 over cases whose model call succeeded on the first attempt."""
    values = sorted(
        c["elapsed_ms"]
        for c in case_results
        if c["status"] != "model_error"
        and len(c.get("attempts") or []) == 1
        and c["attempts"][0].get("outcome") == "ok"
    )

    def nearest_rank(p: float):
        if not values:
            return None
        return values[max(1, math.ceil(p / 100 * len(values))) - 1]

    p95 = nearest_rank(95)
    return {
        "cases": len(values),
        "p50_ms": nearest_rank(50),
        "p95_ms": p95,
        "limit_ms": SC008_MAX_P95_MS,
        "sc008_pass": p95 is not None and p95 < SC008_MAX_P95_MS,
    }


def _decision(case_result: dict):
    output = case_result.get("output")
    if output is None:
        return None
    return [output.get("status"), output.get("policy_result"), output.get("policy_reasons")]


def compute_consistency(current: list[dict], previous: list[dict], compared_with: str) -> dict:
    """SC-007: share of cases with an identical decision in both runs (model_errors excluded)."""
    earlier = {c["id"]: c for c in previous}
    matched = 0
    compared = 0
    mismatches = []
    for case in current:
        other = earlier.get(case["id"])
        if other is None or "model_error" in (case["status"], other["status"]):
            continue
        compared += 1
        if _decision(case) == _decision(other):
            matched += 1
        else:
            mismatches.append(case["id"])
    rate = matched / compared if compared else None
    return {
        "compared_with": compared_with,
        "matched": matched,
        "compared": compared,
        "rate": round(rate, 4) if rate is not None else None,
        "mismatches": mismatches,
        "min_rate": SC007_MIN_RATE,
        "sc007_pass": rate is not None and rate >= SC007_MIN_RATE,
    }


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_summary(doc: dict) -> str:
    counts = doc["counts"]
    cfg = doc["config"]
    latency = doc["latency"]
    by_type = ", ".join(f"{k} {v}" for k, v in sorted(counts["model_errors_by_type"].items()))
    lines = [
        f"# Evaluation run {doc['label']}",
        "",
        f"- Verdict: **{doc['verdict']}**",
        f"- Model: {cfg['model']}, temperature {cfg['temperature']}, {cfg['sdk']}",
        f"- Dataset: {doc['dataset']['path']} ({doc['dataset']['cases_run']} of "
        f"{doc['dataset']['case_count']} cases run, sha256 {doc['dataset']['sha256'][:12]}...)",
        f"- Cases: {counts['total']} total, {counts['scored']} scored, {counts['passed']} passed, "
        f"{counts['failed']} failed, {counts['model_error']} model_error"
        + (f" ({by_type})" if by_type else ""),
        f"- Pass rate: {_pct(doc['pass_rate'])} "
        f"(threshold {_pct(doc['thresholds']['pass_rate'])})",
        f"- Guardrail: {counts['guardrail_passed']}/{counts['guardrail_scored']} "
        f"({_pct(counts['guardrail_rate'])}, threshold 100%)",
        f"- Policy limit: {counts['policy_limit_passed']}/{counts['policy_limit_scored']} "
        f"({_pct(counts['policy_limit_rate'])}, threshold 100%)",
        f"- Retries: {counts['retries']}",
        f"- Latency (SC-008): p50 {latency['p50_ms']} ms, p95 {latency['p95_ms']} ms over "
        f"{latency['cases']} first-attempt cases; "
        f"{'pass' if latency['sc008_pass'] else 'not met'} (p95 < {latency['limit_ms']} ms)",
    ]
    consistency = doc.get("consistency")
    if consistency:
        lines.append(
            f"- Consistency (SC-007) vs {consistency['compared_with']}: "
            f"{consistency['matched']}/{consistency['compared']} = {_pct(consistency['rate'])}; "
            f"{'pass' if consistency['sc007_pass'] else 'not met'} (>= 95%)"
            + (f"; mismatches {', '.join(consistency['mismatches'])}"
               if consistency["mismatches"] else "")
        )
    lines += ["", "| Case | Tags | Status | Failed checks | Quality | Attempts |",
              "|------|------|--------|---------------|---------|----------|"]
    for case in doc["cases"]:
        failed = [c["name"] for c in case["checks"] if not c["passed"]]
        quality = next((c["score"] for c in case["checks"] if c["name"] == "quality"), None)
        status = case["status"]
        if case["model_error"]:
            status = f"model_error: {case['model_error']}"
        lines.append(
            f"| {case['id']} | {', '.join(case['tags'])} | {status} | "
            f"{', '.join(failed) or '-'} | {'-' if quality is None else quality} | "
            f"{len(case['attempts'])} |"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- run


def run(
    cases: list[dict],
    assess_fn: Callable,
    client_factory: Callable,
    out_dir: Path | str,
    label: str,
    *,
    dataset_path: Path | str,
    limit: int | None = None,
    compare_with: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Evaluate `cases`, write the evidence files and return the results document.

    `client_factory()` is called once per case so each case's `last_attempts` is its own.
    """
    out_dir = Path(out_dir)
    dataset_path = Path(dataset_path)
    run_dir = out_dir / "eval-runs" / label
    if run_dir.exists():
        raise LabelExistsError(label)

    previous = None
    if compare_with:
        previous_path = out_dir / "eval-runs" / compare_with / "results.json"
        previous = json.loads(previous_path.read_text(encoding="utf-8"))

    selected = cases[:limit] if limit is not None else list(cases)
    started_at = _now()
    results = []
    for index, case in enumerate(selected):
        result = evaluate_case(case, assess_fn, client_factory())
        results.append(result)
        if result["attempts"] and index < len(selected) - 1:
            sleep(config.CALL_DELAY_SECONDS)  # free-tier pacing (research R4)

    summary = verdict.compute_verdict(results)
    final_verdict = "INCOMPLETE" if len(selected) < len(cases) else summary["verdict"]
    pass_rate = summary["pass_rate"]

    doc = {
        "label": label,
        "started_at": started_at,
        "finished_at": _now(),
        "config": run_config(),
        "dataset": {
            "path": _display_path(dataset_path),
            "case_count": len(cases),
            "cases_run": len(selected),
            "sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        },
        "thresholds": dict(verdict.THRESHOLDS),
        "counts": {
            "total": summary["total"],
            "scored": summary["scored"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "model_error": summary["model_error_count"],
            "model_errors_by_type": summary["model_errors_by_type"],
            "guardrail_passed": summary["guardrail_passed"],
            "guardrail_scored": summary["guardrail_scored"],
            "guardrail_rate": summary["guardrail_rate"],
            "policy_limit_passed": summary["policy_limit_passed"],
            "policy_limit_scored": summary["policy_limit_scored"],
            "policy_limit_rate": summary["policy_limit_rate"],
            "retries": sum(max(0, len(c["attempts"]) - 1) for c in results),
        },
        "pass_rate": None if pass_rate is None else round(pass_rate, 4),
        "verdict": final_verdict,
        "latency": compute_latency(results),
    }
    if previous is not None:
        doc["consistency"] = compute_consistency(results, previous["cases"], compare_with)
    doc["cases"] = results

    run_dir.mkdir(parents=True, exist_ok=False)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    summary_md = render_summary(doc)
    (run_dir / "results.json").write_text(text, encoding="utf-8")
    (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")
    (out_dir / "eval-results.json").write_text(text, encoding="utf-8")

    print(summary_md.split("\n\n| Case")[0])
    print(f"Results: {_display_path(run_dir / 'results.json')}")
    return doc


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Expense Claim Assistant evaluation.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--label", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--compare-with", dest="compare_with", default=None)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    label = args.label or datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in filter(None, (label, args.compare_with)):
        if not LABEL_PATTERN.match(name):
            print(f"error: invalid label {name!r}", file=sys.stderr)
            return EXIT_SETUP_ERROR
    if (out_dir / "eval-runs" / label).exists():
        print(f"error: run label {label!r} already exists; choose a new label", file=sys.stderr)
        return EXIT_LABEL_EXISTS
    if args.compare_with and not (
        out_dir / "eval-runs" / args.compare_with / "results.json"
    ).is_file():
        print(f"error: no results for --compare-with {args.compare_with!r}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    if args.limit is not None and args.limit < 1:
        print("error: --limit must be at least 1", file=sys.stderr)
        return EXIT_SETUP_ERROR

    dataset_path = Path(args.dataset)
    try:
        cases = json.loads(dataset_path.read_text(encoding="utf-8"))["cases"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: cannot load dataset: {type(exc).__name__}", file=sys.stderr)
        return EXIT_SETUP_ERROR

    api_key = config.get_api_key()
    if not api_key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return EXIT_SETUP_ERROR

    from expense.cli import build_client
    from expense.service import assess

    doc = run(
        cases,
        assess,
        lambda: build_client(api_key),
        out_dir,
        label,
        dataset_path=dataset_path,
        limit=args.limit,
        compare_with=args.compare_with,
    )
    return exit_code_for(doc["verdict"])


if __name__ == "__main__":
    raise SystemExit(main())
