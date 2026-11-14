"""Deterministic company policy (FR-050 - FR-059, Constitution III).

The policy table is ground truth and lives here as constants; the model never decides policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

LIMITS_SAR = {"meals": 150, "transport": 200, "accommodation": 600, "office_supplies": 300}
ALWAYS_APPROVAL = frozenset({"client_entertainment", "other"})
NO_RECEIPT_THRESHOLD = 50
MAX_AGE_DAYS = 90

WITHIN_POLICY = "within_policy"
NEEDS_APPROVAL = "needs_manager_approval"

NO_RECEIPT_REASON = "No receipt confirmed for an amount over 50"
CURRENCY_DEFAULTED_NOTE = "Currency not stated; SAR assumed"


@dataclass(frozen=True)
class PolicyDecision:
    result: str
    reasons: tuple[str, ...]


def format_amount(value: float) -> str:
    """Up to 2 decimal places, no trailing zeros (FR-058): 151 -> "151", 150.5 -> "150.5"."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def evaluate(
    category: str,
    amount: float,
    currency: str,
    expense_date: date,
    has_receipt: bool | None,
    nights: int | None,
    today: date,
    currency_defaulted: bool,
) -> PolicyDecision:
    """Apply FR-051 - FR-055 in the FR-057 order, then the FR-024 informational note last.

    Never returns `not_reimbursable` (FR-059).
    """
    reasons: list[str] = []

    # FR-051 / FR-052: limit or category rule.
    if category in ALWAYS_APPROVAL:
        reasons.append(f"Category {category} always requires manager approval")
    elif category in LIMITS_SAR and currency == "SAR":
        if category == "accommodation":
            night_count = nights if nights and nights >= 1 else 1
            limit = LIMITS_SAR["accommodation"] * night_count
            if amount > limit:
                reasons.append(
                    f"Amount {format_amount(amount)} SAR exceeds the accommodation limit of "
                    f"{format_amount(limit)} SAR for {night_count} night(s)"
                )
        else:
            limit = LIMITS_SAR[category]
            if amount > limit:
                reasons.append(
                    f"Amount {format_amount(amount)} SAR exceeds the {category} limit of "
                    f"{format_amount(limit)} SAR"
                )

    # FR-053: receipt (not mentioned counts as no receipt); raw amount, any currency.
    if has_receipt is not True and amount > NO_RECEIPT_THRESHOLD:
        reasons.append(NO_RECEIPT_REASON)

    # FR-054: non-SAR currency, no conversion.
    if currency != "SAR":
        reasons.append(f"Currency {currency} is not SAR; no conversion applied")

    # FR-055: age; exactly 90 days is not older than 90.
    if (today - expense_date).days > MAX_AGE_DAYS:
        reasons.append(f"Expense date is more than 90 days before {today.isoformat()}")

    result = NEEDS_APPROVAL if reasons else WITHIN_POLICY

    # FR-024 / FR-056: informational note, last, never changes the result.
    if currency_defaulted:
        reasons.append(CURRENCY_DEFAULTED_NOTE)

    return PolicyDecision(result=result, reasons=tuple(reasons))
