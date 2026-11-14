"""Quality evaluator (T020; FR-102, FR-103, AC-077)."""

from __future__ import annotations

import pytest

import quality_check


def _case(keywords=("taxi",), **expected) -> dict:
    base = {
        "status": "ok",
        "rejection_reason": None,
        "policy_result": "within_policy",
        "missing_fields": [],
        "category": "transport",
        "amount": 85,
        "expense_date": "2026-11-13",
        "nights": None,
        "description_keywords": list(keywords),
    }
    base.update(expected)
    return {"id": "T-1", "today": "2026-11-14", "expected": base}


def test_all_components_correct_scores_one(sample_outputs):
    result = quality_check.check(_case(keywords=["taxi", "airport"]), sample_outputs["AC-001"])
    assert result.name == "quality"
    assert result.score == pytest.approx(1.0)
    assert result.passed


def test_ac077_wrong_amount_scores_075_and_fails(sample_outputs):
    output = sample_outputs["AC-001"]
    output["amount"] = 86
    result = quality_check.check(_case(), output)
    assert result.score == pytest.approx(0.75)
    assert not result.passed
    assert any("amount" in d for d in result.details)


def test_ac077_fidelity_02_scores_08_and_passes(sample_outputs):
    keywords = ["taxi", "metro", "bus", "tram", "ferry"]  # only "taxi" is in the description
    result = quality_check.check(_case(keywords=keywords), sample_outputs["AC-001"])
    assert result.score == pytest.approx(0.8)
    assert result.passed


def test_expected_null_matches_actual_null(sample_outputs):
    case = _case(keywords=["instructions"], category=None, amount=None, expense_date=None)
    result = quality_check.check(case, sample_outputs["AC-040"])
    assert result.score == pytest.approx(1.0)
    assert result.passed


def test_expected_null_vs_actual_value_is_mismatch(sample_outputs):
    case = _case(category=None, amount=None, expense_date=None)
    result = quality_check.check(case, sample_outputs["AC-001"])  # all three are set
    assert result.score == pytest.approx(0.25)
    assert not result.passed


def test_expected_value_vs_actual_null_is_mismatch(sample_outputs):
    output = sample_outputs["AC-001"]
    output["expense_date"] = None
    assert quality_check.check(_case(), output).score == pytest.approx(0.75)


def test_no_keywords_gives_full_fidelity(sample_outputs):
    output = sample_outputs["AC-001"]
    output["description"] = "something unrelated"
    assert quality_check.check(_case(keywords=[]), output).score == pytest.approx(1.0)


def test_keyword_match_is_case_insensitive(sample_outputs):
    output = sample_outputs["AC-001"]
    output["description"] = "TAXI from the AIRPORT"
    result = quality_check.check(_case(keywords=["taxi", "Airport"]), output)
    assert result.score == pytest.approx(1.0)


def test_multi_word_keyword(sample_outputs):
    output = sample_outputs["AC-001"]
    output["description"] = "Stay at Oasis Inn"
    case = _case(keywords=["Oasis Inn"])
    assert quality_check.check(case, output).score == pytest.approx(1.0)


def test_amount_int_equals_float(sample_outputs):
    output = sample_outputs["AC-001"]
    output["amount"] = 85.0
    assert quality_check.check(_case(), output).score == pytest.approx(1.0)


def test_decimal_amount_must_match_exactly(sample_outputs):
    output = sample_outputs["AC-001"]
    output["amount"] = 150.5
    assert quality_check.check(_case(amount=150.5), output).score == pytest.approx(1.0)
    assert quality_check.check(_case(amount=150), output).score == pytest.approx(0.75)


def test_no_output_scores_zero():
    result = quality_check.check(_case(), None)
    assert result.name == "quality"
    assert result.score == 0.0
    assert not result.passed
