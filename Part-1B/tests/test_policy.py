"""Deterministic company policy (T026; FR-050 - FR-059, AC-006, AC-007, AC-010 - AC-025).

Interface under test (T033):
    evaluate(category, amount, currency, expense_date, has_receipt, nights, today,
             currency_defaulted) -> PolicyDecision(result, reasons)
with `expense_date` and `today` as `datetime.date`.
"""

from __future__ import annotations

import itertools
from datetime import date

import pytest

from expense import policy

TODAY = date(2026, 11, 14)
YESTERDAY = date(2026, 11, 13)
NO_RECEIPT = "No receipt confirmed for an amount over 50"
CURRENCY_NOTE = "Currency not stated; SAR assumed"


def evaluate(category, amount, *, currency="SAR", expense_date=YESTERDAY, has_receipt=True,
             nights=None, today=TODAY, currency_defaulted=False):
    decision = policy.evaluate(
        category=category,
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        has_receipt=has_receipt,
        nights=nights,
        today=today,
        currency_defaulted=currency_defaulted,
    )
    return decision.result, list(decision.reasons)


def test_constants():
    assert policy.LIMITS_SAR == {"meals": 150, "transport": 200, "accommodation": 600,
                                 "office_supplies": 300}
    assert set(policy.ALWAYS_APPROVAL) == {"client_entertainment", "other"}
    assert policy.NO_RECEIPT_THRESHOLD == 50
    assert policy.MAX_AGE_DAYS == 90


def test_ac010_meals_at_limit():
    assert evaluate("meals", 150) == ("within_policy", [])


def test_ac011_meals_over_limit():
    assert evaluate("meals", 151) == (
        "needs_manager_approval", ["Amount 151 SAR exceeds the meals limit of 150 SAR"])


def test_ac012_transport():
    assert evaluate("transport", 200) == ("within_policy", [])
    assert evaluate("transport", 250) == (
        "needs_manager_approval", ["Amount 250 SAR exceeds the transport limit of 200 SAR"])


def test_ac013_accommodation_one_night_default():
    assert evaluate("accommodation", 650) == (
        "needs_manager_approval",
        ["Amount 650 SAR exceeds the accommodation limit of 600 SAR for 1 night(s)"])


def test_ac014_accommodation_two_nights():
    assert evaluate("accommodation", 1300, nights=2) == (
        "needs_manager_approval",
        ["Amount 1300 SAR exceeds the accommodation limit of 1200 SAR for 2 night(s)"])


def test_accommodation_multi_night_within_limit():
    assert evaluate("accommodation", 1100, nights=2) == ("within_policy", [])  # AC-004
    assert evaluate("accommodation", 1200, nights=2) == ("within_policy", [])


def test_ac015_office_supplies():
    assert evaluate("office_supplies", 300) == ("within_policy", [])
    assert evaluate("office_supplies", 301) == (
        "needs_manager_approval",
        ["Amount 301 SAR exceeds the office_supplies limit of 300 SAR"])


def test_ac016_client_entertainment():
    assert evaluate("client_entertainment", 140) == (
        "needs_manager_approval",
        ["Category client_entertainment always requires manager approval"])


def test_ac017_other():
    assert evaluate("other", 90, expense_date=date(2026, 11, 1)) == (
        "needs_manager_approval", ["Category other always requires manager approval"])


def test_ac018_no_receipt_over_50():
    assert evaluate("transport", 60, has_receipt=False) == ("needs_manager_approval",
                                                            [NO_RECEIPT])


def test_ac019_receipt_not_mentioned_counts_as_none():
    assert evaluate("transport", 60, has_receipt=None) == ("needs_manager_approval",
                                                           [NO_RECEIPT])


def test_p09_coffee_receipt_not_mentioned():
    # Dataset case P-09 (spec Revision 3): within the meals limit, only FR-053 triggers.
    assert evaluate("meals", 75, has_receipt=None) == ("needs_manager_approval", [NO_RECEIPT])


def test_no_receipt_at_or_below_50_is_fine():
    assert evaluate("office_supplies", 45, has_receipt=False) == ("within_policy", [])  # AC-003
    assert evaluate("transport", 50, has_receipt=None) == ("within_policy", [])


def test_ac020_usd():
    assert evaluate("transport", 40, currency="USD") == (
        "needs_manager_approval", ["Currency USD is not SAR; no conversion applied"])


def test_ac021_91_days_old():
    assert evaluate("meals", 80, expense_date=date(2026, 8, 15)) == (
        "needs_manager_approval", ["Expense date is more than 90 days before 2026-11-14"])


def test_ac022_exactly_90_days_old():
    assert evaluate("meals", 80, expense_date=date(2026, 8, 16)) == ("within_policy", [])


def test_ac023_reason_order():
    assert evaluate("meals", 200, has_receipt=False, expense_date=date(2026, 8, 1)) == (
        "needs_manager_approval",
        [
            "Amount 200 SAR exceeds the meals limit of 150 SAR",
            NO_RECEIPT,
            "Expense date is more than 90 days before 2026-11-14",
        ],
    )


def test_ac024_eur_no_limit_comparison():
    assert evaluate("accommodation", 700, currency="EUR", nights=1) == (
        "needs_manager_approval", ["Currency EUR is not SAR; no conversion applied"])


def test_ac025_decimal_amount():
    assert evaluate("meals", 150.5) == (
        "needs_manager_approval", ["Amount 150.5 SAR exceeds the meals limit of 150 SAR"])


@pytest.mark.parametrize(("amount", "text"), [
    (151.0, "151"), (150.50, "150.5"), (150.25, "150.25"), (200.1, "200.1"), (1300, "1300"),
])
def test_fr058_amount_formatting(amount, text):
    _, reasons = evaluate("meals", amount)
    assert reasons == [f"Amount {text} SAR exceeds the meals limit of 150 SAR"]


def test_ac006_currency_note_is_last():
    assert evaluate("transport", 85, has_receipt=None, currency_defaulted=True) == (
        "needs_manager_approval", [NO_RECEIPT, CURRENCY_NOTE])


def test_ac007_currency_note_alone_keeps_within_policy():
    assert evaluate("meals", 40, currency_defaulted=True) == ("within_policy", [CURRENCY_NOTE])


def test_fr057_full_order_with_every_rule():
    result, reasons = evaluate("client_entertainment", 500, currency="USD", has_receipt=False,
                               expense_date=date(2026, 1, 1))
    assert result == "needs_manager_approval"
    assert reasons == [
        "Category client_entertainment always requires manager approval",
        NO_RECEIPT,
        "Currency USD is not SAR; no conversion applied",
        "Expense date is more than 90 days before 2026-11-14",
    ]


def test_no_receipt_rule_uses_raw_amount_for_non_sar():
    assert evaluate("transport", 60, currency="USD", has_receipt=False) == (
        "needs_manager_approval", [NO_RECEIPT, "Currency USD is not SAR; no conversion applied"])


def test_fr059_not_reimbursable_never_returned():
    categories = ["meals", "transport", "accommodation", "office_supplies",
                  "client_entertainment", "other"]
    combos = itertools.product(categories, [10, 151, 5000], ["SAR", "USD", "EUR"],
                               [True, False, None], [YESTERDAY, date(2025, 1, 1)])
    for category, amount, currency, receipt, when in combos:
        result, _ = evaluate(category, amount, currency=currency, has_receipt=receipt,
                             expense_date=when)
        assert result in {"within_policy", "needs_manager_approval"}
