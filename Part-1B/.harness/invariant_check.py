"""Invariant evaluator INV-1 .. INV-7 (T017; FR-060 - FR-066, AC-048, AC-049).

Deliberately independent of `src/expense` (it must not import `expense`), so a bug in the
application's own runtime check is caught here. Pure function, no I/O.

INV-4 is applied to `status == "ok"` outputs only: INV-2 requires `policy_result` to be null for
`needs_clarification`, so the limit rule cannot be meant for those outputs.
"""

from __future__ import annotations

import re
from datetime import date

from check_result import CheckResult

LIMITS_SAR = {"meals": 150, "transport": 200, "accommodation": 600, "office_supplies": 300}
CARD_RUN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
FORBIDDEN_WORDS = re.compile(r"\b(approved|paid)\b", re.IGNORECASE)
FREE_TEXT_FIELDS = ("description", "merchant", "clarification_question")


def _strings(value, path: str):
    """Yield (path, string) for every string anywhere in the value."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def check(case: dict, output: dict | None) -> CheckResult:
    if output is None:
        return CheckResult("invariants", False, details=["no output produced"])

    details: list[str] = []
    status = output.get("status")

    # INV-1 (FR-060)
    if status == "ok":
        for key in ("amount", "currency", "category", "expense_date", "policy_result"):
            if output.get(key) is None:
                details.append(f"INV-1: status ok but {key} is null")

    # INV-2 (FR-061)
    if status == "needs_clarification":
        if not output.get("missing_fields"):
            details.append("INV-2: needs_clarification but missing_fields is empty")
        if output.get("clarification_question") is None:
            details.append("INV-2: needs_clarification but clarification_question is null")
        if output.get("policy_result") is not None:
            details.append("INV-2: needs_clarification but policy_result is set")

    # INV-3 (FR-062)
    if status == "rejected":
        if output.get("rejection_reason") is None:
            details.append("INV-3: rejected but rejection_reason is null")
        if output.get("policy_result") is not None:
            details.append("INV-3: rejected but policy_result is set")

    # INV-4 (FR-063)
    category = output.get("category")
    amount = output.get("amount")
    if (
        status == "ok"
        and output.get("currency") == "SAR"
        and category in LIMITS_SAR
        and _is_number(amount)
    ):
        limit = LIMITS_SAR[category]
        if category == "accommodation":
            limit *= (case.get("expected") or {}).get("nights") or 1
        if amount > limit and output.get("policy_result") != "needs_manager_approval":
            details.append(
                f"INV-4: {category} {amount} SAR exceeds limit {limit} SAR but policy_result "
                f"is {output.get('policy_result')!r}"
            )

    # INV-5 (FR-064)
    expense_date = output.get("expense_date")
    if isinstance(expense_date, str):
        try:
            if date.fromisoformat(expense_date) > date.fromisoformat(case["today"]):
                details.append(f"INV-5: expense_date {expense_date} is after {case['today']}")
        except ValueError:
            details.append(f"INV-5: expense_date {expense_date!r} is not a valid date")

    # INV-6 (FR-065)
    for path, text in _strings(output, ""):
        if CARD_RUN.search(text):
            details.append(f"INV-6: unmasked card number in {path}")

    # INV-7 (FR-066)
    free_text = [(key, output.get(key)) for key in FREE_TEXT_FIELDS]
    free_text += [
        (f"policy_reasons[{i}]", reason)
        for i, reason in enumerate(output.get("policy_reasons") or [])
    ]
    for path, text in free_text:
        if isinstance(text, str):
            match = FORBIDDEN_WORDS.search(text)
            if match:
                details.append(f"INV-7: forbidden word {match.group(0)!r} in {path}")

    return CheckResult("invariants", not details, details=details)
