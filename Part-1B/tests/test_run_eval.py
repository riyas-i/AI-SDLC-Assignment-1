"""Evaluation runner (T024; FR-085, FR-104 - FR-106, AC-079, SC-007, SC-008, contracts/cli.md).

Uses an injected fake `assess` function: no model, no network, no key file.
Imports `expense.config` and `expense.llm_client` through run_eval, so it fails with ImportError
until Phase 4.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import pytest
from expense.llm_client import AttemptRecord, ModelError

import run_eval
from expense import config

N_CASES = 24


def _make_case(i: int) -> dict:
    tags = [["standard"], ["guardrail"], ["policy_limit"], ["clarification"]][i % 4]
    return {
        "id": f"X-{i:02d}",
        "kind": "normal",
        "tags": tags,
        "input": f"taxi {10 + i} SAR yesterday, have receipt",
        "today": "2026-11-14",
        "expected": {
            "status": "ok",
            "rejection_reason": None,
            "policy_result": "within_policy",
            "missing_fields": [],
            "category": "transport",
            "amount": 10 + i,
            "expense_date": "2026-11-13",
            "nights": None,
            "description_keywords": ["taxi"],
        },
        "spec_ref": "test",
    }


def _output_for(case: dict, **overrides) -> dict:
    e = case["expected"]
    out = {
        "status": e["status"],
        "category": e["category"],
        "amount": e["amount"],
        "currency": "SAR",
        "expense_date": e["expense_date"],
        "merchant": None,
        "has_receipt": True,
        "description": "Taxi ride",
        "policy_result": e["policy_result"],
        "policy_reasons": [],
        "missing_fields": [],
        "clarification_question": None,
        "rejection_reason": None,
    }
    out.update(overrides)
    return out


def _ok(n: int = 1) -> list:
    """`n` attempts: n-1 network failures, then success."""
    records = [AttemptRecord(attempt=k, outcome="network", elapsed_ms=5) for k in range(1, n)]
    return records + [AttemptRecord(attempt=n, outcome="ok", elapsed_ms=10)]


class FakeClient:
    def __init__(self):
        self.last_attempts: list = []


class FakeAssess:
    """Maps input text → behaviour: {"output": dict, "attempts": [...]} or {"error": ...}."""

    def __init__(self, cases: list[dict], overrides: dict | None = None):
        self.plan = {c["input"]: {"output": _output_for(c), "attempts": _ok()} for c in cases}
        for case_id, behaviour in (overrides or {}).items():
            case = next(c for c in cases if c["id"] == case_id)
            self.plan[case["input"]] = behaviour
        self.calls = 0

    def __call__(self, text, today, client):
        self.calls += 1
        behaviour = self.plan[text]
        client.last_attempts = list(behaviour.get("attempts", []))
        if "error" in behaviour:
            raise ModelError(behaviour["error"], attempts=behaviour["attempts"])
        return behaviour["output"]


@pytest.fixture
def cases() -> list[dict]:
    return [_make_case(i) for i in range(N_CASES)]


@pytest.fixture
def dataset_file(tmp_path, cases) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return path


@pytest.fixture
def waits() -> list[float]:
    return []


def _run(cases, assess, out, label, dataset_file, waits, **kwargs) -> dict:
    return run_eval.run(cases, assess, FakeClient, out, label, dataset_path=dataset_file,
                        sleep=waits.append, **kwargs)


# --------------------------------------------------------------------------- files


def test_writes_results_summary_and_latest_copy(tmp_path, cases, dataset_file, waits, capsys):
    out = tmp_path / "evidence"
    doc = _run(cases, FakeAssess(cases), out, "first", dataset_file, waits)
    run_dir = out / "eval-runs" / "first"
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    assert results == json.loads(json.dumps(doc))
    assert (run_dir / "summary.md").is_file()
    assert (out / "eval-results.json").read_text(encoding="utf-8") == (
        run_dir / "results.json"
    ).read_text(encoding="utf-8")
    assert doc["verdict"] == "PASS"
    assert "PASS" in (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "PASS" in capsys.readouterr().out


def test_existing_label_is_refused(tmp_path, cases, dataset_file, waits):
    out = tmp_path / "evidence"
    _run(cases, FakeAssess(cases), out, "dup", dataset_file, waits)
    before = (out / "eval-runs" / "dup" / "results.json").read_bytes()
    with pytest.raises(run_eval.LabelExistsError):
        _run(cases, FakeAssess(cases), out, "dup", dataset_file, waits)
    assert (out / "eval-runs" / "dup" / "results.json").read_bytes() == before


def test_main_refuses_existing_label_with_exit_1(tmp_path, dataset_file):
    out = tmp_path / "evidence"
    (out / "eval-runs" / "taken").mkdir(parents=True)
    rc = run_eval.main(["--label", "taken", "--out", str(out), "--dataset", str(dataset_file)])
    assert rc == 1


def test_main_without_key_is_setup_error(tmp_path, dataset_file, capsys):
    rc = run_eval.main(["--label", "nokey", "--out", str(tmp_path / "evidence"),
                        "--dataset", str(dataset_file)])
    assert rc == 3
    assert "GEMINI_API_KEY is not set" in capsys.readouterr().err
    assert not (tmp_path / "evidence" / "eval-runs" / "nokey").exists()


# --------------------------------------------------------------------------- recorded metadata


def test_records_configuration_and_thresholds(tmp_path, cases, dataset_file, waits):
    doc = _run(cases, FakeAssess(cases), tmp_path / "ev", "meta", dataset_file, waits)
    cfg = doc["config"]
    assert cfg["model"] == "gemini-3.5-flash" == config.MODEL_NAME  # spec Revision 4
    assert cfg["temperature"] == 0.0
    assert cfg["call_delay_seconds"] == config.CALL_DELAY_SECONDS
    assert cfg["timeout_seconds"] == config.TIMEOUT_SECONDS
    assert cfg["retry_policy"]["max_attempts"] == 4
    assert cfg["retry_policy"]["backoff_seconds"] == [1, 2, 4]
    assert importlib.metadata.version("google-genai") in cfg["sdk"]
    assert cfg["python"]
    assert doc["dataset"]["sha256"] == hashlib.sha256(dataset_file.read_bytes()).hexdigest()
    assert doc["dataset"]["case_count"] == N_CASES
    assert doc["thresholds"] == {
        "case_quality": 0.8,
        "pass_rate": 0.85,
        "guardrail_rate": 1.0,
        "policy_limit_rate": 1.0,
        "max_model_errors": 2,
    }
    for case in doc["cases"]:
        assert [c["name"] for c in case["checks"]] == ["schema", "invariants", "outcome",
                                                         "quality"]
        assert case["attempts"] == [{"attempt": 1, "outcome": "ok", "elapsed_ms": 10}]


def test_key_never_written(tmp_path, cases, dataset_file, waits, fake_key, capsys):
    overrides = {"X-03": {"error": "api_error", "attempts": [
        AttemptRecord(attempt=1, outcome="api_error", elapsed_ms=3)]}}
    out = tmp_path / "evidence"
    _run(cases, FakeAssess(cases, overrides), out, "secret", dataset_file, waits)
    for path in out.rglob("*"):
        if path.is_file():
            assert fake_key not in path.read_text(encoding="utf-8"), path
    captured = capsys.readouterr()
    assert fake_key not in captured.out + captured.err


def test_sleeps_between_model_calls_only(tmp_path, cases, dataset_file, waits):
    _run(cases, FakeAssess(cases), tmp_path / "ev", "pace", dataset_file, waits)
    assert waits and all(w == config.CALL_DELAY_SECONDS for w in waits)
    assert len(waits) <= N_CASES - 1


# --------------------------------------------------------------------------- model errors


def test_model_error_recorded_with_attempts_and_excluded(tmp_path, cases, dataset_file, waits):
    attempts = [AttemptRecord(attempt=k, outcome="quota", elapsed_ms=4) for k in range(1, 5)]
    overrides = {"X-05": {"error": "quota", "attempts": attempts}}
    doc = _run(cases, FakeAssess(cases, overrides), tmp_path / "ev", "me", dataset_file, waits)
    case = next(c for c in doc["cases"] if c["id"] == "X-05")
    assert case["status"] == "model_error"
    assert case["model_error"] == "quota"
    assert case["output"] is None
    assert [a["outcome"] for a in case["attempts"]] == ["quota"] * 4
    assert doc["counts"]["model_error"] == 1
    assert doc["counts"]["model_errors_by_type"] == {"quota": 1}
    assert doc["counts"]["scored"] == N_CASES - 1
    assert doc["verdict"] == "PASS"


def test_three_model_errors_inconclusive(tmp_path, cases, dataset_file, waits):
    overrides = {
        cid: {"error": "timeout", "attempts": [AttemptRecord(1, "timeout", 30000)]}
        for cid in ("X-00", "X-01", "X-02")
    }
    doc = _run(cases, FakeAssess(cases, overrides), tmp_path / "ev", "inc", dataset_file, waits)
    assert doc["verdict"] == "INCONCLUSIVE"
    assert run_eval.exit_code_for(doc["verdict"]) == 2


def test_retried_success_records_attempts(tmp_path, cases, dataset_file, waits):
    overrides = {"X-04": {"output": _output_for(cases[4]), "attempts": _ok(2)}}
    doc = _run(cases, FakeAssess(cases, overrides), tmp_path / "ev", "retry", dataset_file, waits)
    case = next(c for c in doc["cases"] if c["id"] == "X-04")
    assert case["status"] == "pass"
    assert [a["outcome"] for a in case["attempts"]] == ["network", "ok"]
    assert doc["counts"]["retries"] == 1


def test_failing_case_and_fail_verdict(tmp_path, cases, dataset_file, waits):
    wrong = _output_for(cases[1], status="rejected", category=None, amount=None, currency=None,
                        expense_date=None, has_receipt=None, policy_result=None,
                        rejection_reason="prompt_injection")
    overrides = {"X-01": {"output": wrong, "attempts": _ok()}}  # X-01 is a guardrail case
    doc = _run(cases, FakeAssess(cases, overrides), tmp_path / "ev", "fail", dataset_file, waits)
    case = next(c for c in doc["cases"] if c["id"] == "X-01")
    assert case["status"] == "fail"
    assert doc["verdict"] == "FAIL"
    assert run_eval.exit_code_for("FAIL") == 1
    assert run_eval.exit_code_for("PASS") == 0


# --------------------------------------------------------------------------- --limit


def test_limit_gives_incomplete(tmp_path, cases, dataset_file, waits):
    doc = _run(cases, FakeAssess(cases), tmp_path / "ev", "lim", dataset_file, waits, limit=3)
    assert len(doc["cases"]) == 3
    assert doc["verdict"] == "INCOMPLETE"
    assert run_eval.exit_code_for(doc["verdict"]) == 3


# --------------------------------------------------------------------------- SC-008 latency


def _latency_case(cid, status="pass", attempts=1, elapsed=0, last_outcome="ok") -> dict:
    records = [{"attempt": k, "outcome": "network", "elapsed_ms": 1} for k in range(1, attempts)]
    if attempts:
        records.append({"attempt": attempts, "outcome": last_outcome, "elapsed_ms": elapsed})
    return {"id": cid, "status": status, "attempts": records, "elapsed_ms": elapsed}


def test_latency_nearest_rank_over_first_attempt_cases():
    results = [_latency_case(f"A{i}", elapsed=100 * i) for i in range(1, 21)]  # 100..2000
    results.append(_latency_case("retried", attempts=2, elapsed=99999))
    results.append(_latency_case("no-model", attempts=0, elapsed=50000))
    results.append(_latency_case("err", status="model_error", elapsed=60000,
                                 last_outcome="timeout"))
    latency = run_eval.compute_latency(results)
    assert latency["cases"] == 20
    assert latency["p50_ms"] == 1000
    assert latency["p95_ms"] == 1900
    assert latency["sc008_pass"] is True


def test_latency_over_limit_fails():
    results = [_latency_case(f"A{i}", elapsed=16000) for i in range(5)]
    assert run_eval.compute_latency(results)["sc008_pass"] is False


def test_latency_without_model_cases():
    latency = run_eval.compute_latency([_latency_case("x", attempts=0)])
    assert latency["p50_ms"] is None and latency["p95_ms"] is None
    assert latency["sc008_pass"] is False


def test_latency_block_in_results_and_summary(tmp_path, cases, dataset_file, waits):
    doc = _run(cases, FakeAssess(cases), tmp_path / "ev", "lat", dataset_file, waits)
    assert {"p50_ms", "p95_ms", "sc008_pass"} <= set(doc["latency"])
    summary = (tmp_path / "ev" / "eval-runs" / "lat" / "summary.md").read_text(encoding="utf-8")
    assert "p95" in summary


# --------------------------------------------------------------------------- SC-007 consistency


def test_compare_with_23_of_24_matching(tmp_path, cases, dataset_file, waits, capsys):
    out = tmp_path / "evidence"
    _run(cases, FakeAssess(cases), out, "run-a", dataset_file, waits)
    changed = _output_for(cases[0], policy_result="needs_manager_approval",
                          policy_reasons=["No receipt confirmed for an amount over 50"])
    overrides = {"X-00": {"output": changed, "attempts": _ok()}}
    doc = _run(cases, FakeAssess(cases, overrides), out, "run-b", dataset_file, waits,
               compare_with="run-a")
    consistency = doc["consistency"]
    assert consistency["compared_with"] == "run-a"
    assert consistency["matched"] == 23
    assert consistency["compared"] == 24
    assert consistency["rate"] == 0.9583
    assert consistency["mismatches"] == ["X-00"]
    assert consistency["sc007_pass"] is True
    saved = json.loads((out / "eval-runs" / "run-b" / "results.json").read_text("utf-8"))
    assert saved["consistency"] == consistency
    assert "SC-007" in (out / "eval-runs" / "run-b" / "summary.md").read_text("utf-8")
    assert "SC-007" in capsys.readouterr().out


def test_compare_with_excludes_model_errors_in_either_run(tmp_path, cases, dataset_file, waits):
    out = tmp_path / "evidence"
    first = {"X-02": {"error": "server", "attempts": [AttemptRecord(1, "server", 5)]}}
    _run(cases, FakeAssess(cases, first), out, "run-a", dataset_file, waits)
    second = {"X-07": {"error": "network", "attempts": [AttemptRecord(1, "network", 5)]}}
    doc = _run(cases, FakeAssess(cases, second), out, "run-b", dataset_file, waits,
               compare_with="run-a")
    assert doc["consistency"]["compared"] == 22
    assert doc["consistency"]["matched"] == 22
    assert doc["consistency"]["rate"] == 1.0


def test_consistency_below_95_percent_fails():
    def result(cid, policy):
        return {"id": cid, "status": "pass",
                "output": {"status": "ok", "policy_result": policy, "policy_reasons": []}}

    previous = [result(f"C{i}", "within_policy") for i in range(10)]
    current = [result(f"C{i}", "within_policy" if i else "needs_manager_approval")
               for i in range(10)]
    consistency = run_eval.compute_consistency(current, previous, "old")
    assert consistency["rate"] == 0.9
    assert consistency["sc007_pass"] is False
