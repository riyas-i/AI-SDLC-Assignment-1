"""Outcome evaluator (T018; FR-041, FR-102, AC-080, AC-081)."""

from __future__ import annotations

import outcome_check


def _case(**expected) -> dict:
    base = {
        "status": "ok",
        "rejection_reason": None,
        "policy_result": "within_policy",
        "missing_fields": [],
        "category": "transport",
        "amount": 85,
        "expense_date": "2026-11-13",
        "nights": None,
        "description_keywords": [],
    }
    base.update(expected)
    return {"id": "T-1", "today": "2026-11-14", "expected": base}


def test_exact_match_passes(sample_outputs):
    result = outcome_check.check(_case(), sample_outputs["AC-001"])
    assert result.name == "outcome"
    assert result.passed
    assert result.details == []


def test_ac080_expected_rejection_got_ok_fails(sample_outputs):
    case = _case(status="rejected", rejection_reason="prompt_injection", policy_result=None)
    result = outcome_check.check(case, sample_outputs["AC-001"])
    assert not result.passed
    assert any("status" in d for d in result.details)
    assert any("rejection_reason" in d for d in result.details)


def test_ac081_extra_missing_field_fails(sample_outputs):
    case = _case(status="needs_clarification", policy_result=None, missing_fields=["amount"])
    output = sample_outputs["AC-030"]
    output["missing_fields"] = ["amount", "expense_date"]
    result = outcome_check.check(case, output)
    assert not result.passed
    assert any("missing_fields" in d for d in result.details)


def test_policy_result_mismatch_fails(sample_outputs):
    result = outcome_check.check(_case(policy_result="needs_manager_approval"),
                                 sample_outputs["AC-001"])
    assert not result.passed
    assert any("policy_result" in d for d in result.details)


def test_missing_fields_order_matters(sample_outputs):
    case = _case(status="needs_clarification", policy_result=None,
                 missing_fields=["amount", "category"])
    output = sample_outputs["AC-030"]
    output["missing_fields"] = ["category", "amount"]
    assert not outcome_check.check(case, output).passed
    output["missing_fields"] = ["amount", "category"]
    assert outcome_check.check(case, output).passed


def test_quality_fields_are_not_compared(sample_outputs):
    output = sample_outputs["AC-001"]
    output["amount"] = 999
    output["category"] = "meals"
    assert outcome_check.check(_case(), output).passed


def test_no_output_fails():
    result = outcome_check.check(_case(), None)
    assert result.name == "outcome" and not result.passed and result.details
