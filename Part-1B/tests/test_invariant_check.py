"""Invariant evaluator INV-1 .. INV-7 (T016; FR-060 - FR-066, AC-048, AC-049)."""

from __future__ import annotations

import pytest

import invariant_check


def _case(today="2026-11-14", nights=None) -> dict:
    return {"id": "T-1", "today": today, "expected": {"nights": nights}}


def _assert_fails(result, inv: str):
    assert result.name == "invariants"
    assert not result.passed
    assert any(d.startswith(inv) for d in result.details), result.details


def test_all_sample_outputs_pass(sample_outputs):
    for ac_id, output in sample_outputs.items():
        result = invariant_check.check(_case(), output)
        assert result.passed, (ac_id, result.details)
        assert result.details == []


# INV-1 (FR-060) -------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["amount", "currency", "category", "expense_date",
                                   "policy_result"])
def test_inv1_ok_requires_fields(sample_outputs, field):
    output = sample_outputs["AC-001"]
    output[field] = None
    _assert_fails(invariant_check.check(_case(), output), "INV-1")


def test_inv1_passes(sample_outputs):
    assert invariant_check.check(_case(), sample_outputs["AC-001"]).passed


# INV-2 (FR-061) -------------------------------------------------------------------------


def test_inv2_empty_missing_fields_fails(sample_outputs):
    output = sample_outputs["AC-030"]
    output["missing_fields"] = []
    _assert_fails(invariant_check.check(_case(), output), "INV-2")


def test_inv2_null_question_fails(sample_outputs):
    output = sample_outputs["AC-030"]
    output["clarification_question"] = None
    _assert_fails(invariant_check.check(_case(), output), "INV-2")


def test_inv2_policy_result_set_fails(sample_outputs):
    output = sample_outputs["AC-030"]
    output["policy_result"] = "within_policy"
    _assert_fails(invariant_check.check(_case(), output), "INV-2")


def test_inv2_passes(sample_outputs):
    assert invariant_check.check(_case(), sample_outputs["AC-030"]).passed


# INV-3 (FR-062) -------------------------------------------------------------------------


def test_inv3_policy_result_set_fails(sample_outputs):
    output = sample_outputs["AC-040"]
    output["policy_result"] = "needs_manager_approval"
    _assert_fails(invariant_check.check(_case(), output), "INV-3")


def test_inv3_missing_reason_fails(sample_outputs):
    output = sample_outputs["AC-040"]
    output["rejection_reason"] = None
    _assert_fails(invariant_check.check(_case(), output), "INV-3")


def test_inv3_passes(sample_outputs):
    assert invariant_check.check(_case(), sample_outputs["AC-040"]).passed


# INV-4 (FR-063) -------------------------------------------------------------------------


def test_inv4_meals_over_limit_within_policy_fails(sample_outputs):
    output = sample_outputs["AC-011"]  # meals 151 SAR
    output["policy_result"] = "within_policy"
    output["policy_reasons"] = []
    _assert_fails(invariant_check.check(_case(), output), "INV-4")


def test_inv4_meals_over_limit_needs_approval_passes(sample_outputs):
    assert invariant_check.check(_case(), sample_outputs["AC-011"]).passed


def test_inv4_accommodation_uses_case_nights(make_claim):
    output = make_claim(
        status="ok", category="accommodation", amount=1100, currency="SAR",
        expense_date="2026-11-10", merchant="Oasis Inn", has_receipt=True,
        description="Oasis Inn hotel, 2 nights", policy_result="within_policy",
    )
    assert invariant_check.check(_case(nights=2), output).passed
    _assert_fails(invariant_check.check(_case(nights=None), output), "INV-4")  # 600 × 1


def test_inv4_not_applied_to_non_sar(make_claim):
    output = make_claim(
        status="ok", category="meals", amount=900, currency="USD", expense_date="2026-11-13",
        description="Dinner", policy_result="within_policy",
    )
    result = invariant_check.check(_case(), output)
    assert not any(d.startswith("INV-4") for d in result.details)


def test_inv4_boundary_equal_to_limit_passes(make_claim):
    output = make_claim(
        status="ok", category="transport", amount=200, currency="SAR",
        expense_date="2026-11-13", description="Taxi", has_receipt=True,
        policy_result="within_policy",
    )
    assert invariant_check.check(_case(), output).passed


# INV-5 (FR-064) -------------------------------------------------------------------------


def test_inv5_future_date_fails(sample_outputs):
    output = sample_outputs["AC-001"]
    output["expense_date"] = "2026-11-15"
    _assert_fails(invariant_check.check(_case(today="2026-11-14"), output), "INV-5")


def test_inv5_today_passes(sample_outputs):
    output = sample_outputs["AC-001"]
    output["expense_date"] = "2026-11-14"
    assert invariant_check.check(_case(today="2026-11-14"), output).passed


# INV-6 (FR-065) -------------------------------------------------------------------------


def test_inv6_card_in_description_fails(sample_outputs):
    output = sample_outputs["AC-048"]
    output["description"] = "Lunch, card 4111-1111-1111-1111"
    _assert_fails(invariant_check.check(_case(), output), "INV-6")


def test_inv6_card_in_merchant_fails(sample_outputs):
    output = sample_outputs["AC-048"]
    output["merchant"] = "Cafe 4111111111111111"
    _assert_fails(invariant_check.check(_case(), output), "INV-6")


def test_inv6_card_in_list_item_fails(sample_outputs):
    output = sample_outputs["AC-011"]
    output["policy_reasons"] = ["card 4111 1111 1111 1111"]
    _assert_fails(invariant_check.check(_case(), output), "INV-6")


def test_inv6_masked_card_passes(sample_outputs):
    output = sample_outputs["AC-048"]
    output["description"] = "Lunch, card ************1111"
    assert invariant_check.check(_case(), output).passed


def test_inv6_short_numbers_pass(sample_outputs):
    output = sample_outputs["AC-048"]
    output["description"] = "Lunch 2026-11-13 ref 123456789012"  # 12 digits: not a card
    assert invariant_check.check(_case(), output).passed


# INV-7 (FR-066) -------------------------------------------------------------------------


def test_inv7_paid_in_description_fails(sample_outputs):
    output = sample_outputs["AC-001"]
    output["description"] = "Taxi paid by card"
    _assert_fails(invariant_check.check(_case(), output), "INV-7")


def test_inv7_approved_in_reason_fails(sample_outputs):
    output = sample_outputs["AC-011"]
    output["policy_reasons"] = ["Approved by policy"]
    _assert_fails(invariant_check.check(_case(), output), "INV-7")


def test_inv7_pre_approved_in_merchant_fails(sample_outputs):
    output = sample_outputs["AC-001"]
    output["merchant"] = "pre-approved vendor"
    _assert_fails(invariant_check.check(_case(), output), "INV-7")


def test_inv7_approved_in_question_fails(sample_outputs):
    output = sample_outputs["AC-030"]
    output["clarification_question"] = "Is this APPROVED?"
    _assert_fails(invariant_check.check(_case(), output), "INV-7")


def test_inv7_neutral_words_pass(sample_outputs):
    output = sample_outputs["AC-001"]
    output["description"] = "Taxi spent by card, pre-cleared trip, unpaid-ish approval form"
    # "unpaid" and "approval" are not the whole words "paid" / "approved".
    result = invariant_check.check(_case(), output)
    assert result.passed, result.details


# Combined ---------------------------------------------------------------------------------


def test_every_violation_is_reported(sample_outputs):
    output = sample_outputs["AC-011"]
    output["policy_result"] = "within_policy"
    output["expense_date"] = "2026-12-01"
    output["description"] = "Dinner paid with 4111111111111111"
    details = invariant_check.check(_case(), output).details
    for inv in ("INV-4", "INV-5", "INV-6", "INV-7"):
        assert any(d.startswith(inv) for d in details), (inv, details)


def test_no_output_fails():
    result = invariant_check.check(_case(), None)
    assert result.name == "invariants" and not result.passed and result.details
