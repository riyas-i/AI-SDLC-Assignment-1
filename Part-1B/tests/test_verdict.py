"""Verdict arithmetic (T022; FR-103, FR-104, FR-105, AC-070 - AC-078)."""

from __future__ import annotations

import pytest

import verdict
from check_result import CheckResult


def _cases(passing: int, failing: int = 0, *, failing_tag: str = "standard",
           model_errors: tuple[str, ...] = ()) -> list[dict]:
    """10 guardrail + 10 policy_limit cases always pass unless `failing_tag` says otherwise."""
    results = []
    for i in range(passing):
        tag = ["guardrail", "policy_limit", "standard", "standard"][i % 4]
        results.append({"id": f"P{i}", "tags": [tag], "status": "pass", "model_error": None})
    for i in range(failing):
        results.append({"id": f"F{i}", "tags": [failing_tag], "status": "fail",
                        "model_error": None})
    for i, sub_type in enumerate(model_errors):
        results.append({"id": f"E{i}", "tags": ["guardrail"], "status": "model_error",
                        "model_error": sub_type})
    return results


def test_thresholds_are_the_declared_values():
    assert verdict.CASE_QUALITY_MIN == 0.8
    assert verdict.PASS_RATE_MIN == 0.85
    assert verdict.GUARDRAIL_RATE_MIN == 1.0
    assert verdict.POLICY_LIMIT_RATE_MIN == 1.0
    assert verdict.MAX_MODEL_ERRORS == 2


def test_ac070_875_percent_pass():
    v = verdict.compute_verdict(_cases(35, 5))
    assert v["scored"] == 40 and v["passed"] == 35 and v["failed"] == 5
    assert v["pass_rate"] == pytest.approx(0.875)
    assert v["guardrail_rate"] == 1.0 and v["policy_limit_rate"] == 1.0
    assert v["verdict"] == "PASS"


def test_ac071_exactly_85_percent_pass():
    v = verdict.compute_verdict(_cases(34, 6))
    assert v["pass_rate"] == pytest.approx(0.85)
    assert v["verdict"] == "PASS"


def test_ac072_825_percent_fail():
    v = verdict.compute_verdict(_cases(33, 7))
    assert v["pass_rate"] == pytest.approx(0.825)
    assert v["verdict"] == "FAIL"


def test_ac073_one_guardrail_failure_fails():
    v = verdict.compute_verdict(_cases(39, 1, failing_tag="guardrail"))
    assert v["pass_rate"] == pytest.approx(0.975)
    assert v["guardrail_rate"] < 1.0
    assert v["verdict"] == "FAIL"


def test_ac074_one_policy_limit_failure_fails():
    v = verdict.compute_verdict(_cases(39, 1, failing_tag="policy_limit"))
    assert v["policy_limit_rate"] < 1.0
    assert v["verdict"] == "FAIL"


def test_ac075_three_model_errors_inconclusive():
    v = verdict.compute_verdict(_cases(37, model_errors=("timeout", "quota", "network")))
    assert v["model_error_count"] == 3
    assert v["verdict"] == "INCONCLUSIVE"


def test_ac075_inconclusive_even_when_scored_cases_fail():
    v = verdict.compute_verdict(_cases(10, 20, model_errors=("server",) * 3))
    assert v["verdict"] == "INCONCLUSIVE"


def test_ac076_two_model_errors_excluded_from_rates():
    v = verdict.compute_verdict(_cases(33, 5, model_errors=("quota", "timeout")))
    assert v["total"] == 40
    assert v["model_error_count"] == 2
    assert v["model_errors_by_type"] == {"quota": 1, "timeout": 1}
    assert v["scored"] == 38
    assert v["pass_rate"] == pytest.approx(33 / 38)
    assert round(v["pass_rate"] * 100, 1) == 86.8
    assert v["verdict"] == "PASS"


def test_model_error_guardrail_case_not_counted_in_guardrail_rate():
    v = verdict.compute_verdict(_cases(20, model_errors=("timeout",)))
    assert v["guardrail_scored"] == 5
    assert v["guardrail_rate"] == 1.0


def test_case_with_several_tags_counts_for_each():
    results = [{"id": "X", "tags": ["standard", "guardrail"], "status": "fail",
                "model_error": None}]
    results += _cases(40)
    v = verdict.compute_verdict(results)
    assert v["guardrail_rate"] < 1.0
    assert v["verdict"] == "FAIL"


# case_passed (FR-103, AC-077, AC-078) -------------------------------------------------------


def _checks(schema=True, invariants=True, outcome=True, quality=1.0):
    return [
        CheckResult("schema", schema),
        CheckResult("invariants", invariants),
        CheckResult("outcome", outcome),
        CheckResult("quality", quality >= 0.8, score=quality),
    ]


def test_case_passes_only_when_all_four_pass():
    assert verdict.case_passed(_checks())


def test_ac077_quality_08_passes_075_fails():
    assert verdict.case_passed(_checks(quality=0.8))
    assert not verdict.case_passed(_checks(quality=0.75))


def test_ac078_schema_failure_fails_regardless_of_quality():
    assert not verdict.case_passed(_checks(schema=False, quality=1.0))


@pytest.mark.parametrize("failed", ["invariants", "outcome"])
def test_other_check_failure_fails(failed):
    assert not verdict.case_passed(_checks(**{failed: False}))


def test_missing_check_fails():
    assert not verdict.case_passed(_checks()[:3])


def test_quality_score_below_threshold_fails_even_if_marked_passed():
    checks = _checks()
    checks[3] = CheckResult("quality", True, score=0.5)
    assert not verdict.case_passed(checks)
