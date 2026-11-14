"""Claim assessment: guardrails, status decision, clarification, policy and output checks.

Order of processing (plan Design Notes): validate input → mask → injection phrase check →
prohibited keyword check → model extraction → status decision → policy (if `ok`) → assemble →
truncate / sanitise wording / mask output → schema validation → invariant check → return.

Every decision here is deterministic; the model only supplies the extraction (Constitution III).
"""

from __future__ import annotations

import json
import re
from datetime import date

from jsonschema import Draft202012Validator

from expense import config, extractor, policy
from expense.masking import find_unmasked_card_numbers, mask_card_numbers, mask_output

SCHEMA_KEY_ORDER = (
    "status",
    "category",
    "amount",
    "currency",
    "expense_date",
    "merchant",
    "has_receipt",
    "description",
    "policy_result",
    "policy_reasons",
    "missing_fields",
    "clarification_question",
    "rejection_reason",
)

SUPPORTED_CURRENCIES = ("SAR", "USD", "EUR")
MERCHANT_MAX = 80
DESCRIPTION_MAX = 120
FIELD_ORDER = ("amount", "category", "expense_date")
FIELD_NAMES = {"amount": "amount", "category": "category", "expense_date": "expense date"}

# FR-031: deterministic prompt-injection phrases (case-insensitive, whole words).
INJECTION_PHRASES = (
    "ignore your rules",
    "ignore previous instructions",
    "ignore all instructions",
    "approve this",
    "approve it",
    "mark as approved",
    "set policy_result",
    "you are now",
    "system prompt",
)

# FR-033: deterministic prohibited-item keywords (case-insensitive, whole words).
PROHIBITED_KEYWORDS = (
    "alcohol",
    "beer",
    "wine",
    "whisky",
    "vodka",
    "liquor",
    "traffic fine",
    "parking fine",
    "speeding ticket",
    "traffic ticket",
)

# Research R7: fixed neutral descriptions for rejected outputs (FR-034).
REJECTED_DESCRIPTIONS = {
    "prompt_injection": "Request contains instructions to change the assistant's rules",
    "out_of_scope": "Request is not an expense claim",
    "prohibited_item": "Expense is a prohibited item under company policy",
}

MULTIPLE_EXPENSES_QUESTION = (
    "Please submit one expense per claim. Which single expense do you want to claim?"
)


def _phrase_regex(phrases: tuple[str, ...]) -> re.Pattern[str]:
    parts = [r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in phrases]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_INJECTION_RE = _phrase_regex(INJECTION_PHRASES)
_PROHIBITED_RE = _phrase_regex(PROHIBITED_KEYWORDS)
_FORBIDDEN_WORD_RE = re.compile(r"\b(approved|paid)\b", re.IGNORECASE)
_REPLACEMENTS = {"approved": "cleared", "paid": "spent"}

_CLAIM_VALIDATOR = Draft202012Validator(
    json.loads(config.CLAIM_SCHEMA_PATH.read_text(encoding="utf-8"))
)


class UsageError(ValueError):
    """Invalid input text (FR-003). The CLI reports it as `usage error: <reason>`, exit 1."""


class InternalError(Exception):
    """The final output failed the schema or an invariant (FR-011). CLI exit 3."""

    def __init__(self, check: str) -> None:
        super().__init__(check)
        self.check = check

    def __str__(self) -> str:
        return self.check


# --------------------------------------------------------------------------- text helpers


def _sanitise(text: str) -> str:
    """Replace the whole words `approved` / `paid` with neutral wording (FR-072, research R6)."""

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        new = _REPLACEMENTS[word.lower()]
        if word.isupper() and len(word) > 1:
            return new.upper()
        if word[0].isupper():
            return new.capitalize()
        return new

    return _FORBIDDEN_WORD_RE.sub(replace, text)


def _clean_text(text: str, limit: int | None = None) -> str:
    """Mask, sanitise and truncate until stable, so no step can undo another (FR-071 - FR-073)."""
    for _ in range(5):
        new = _sanitise(mask_card_numbers(text))
        if limit is not None:
            new = new[:limit]
        if new == text:
            break
        text = new
    return text


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


# --------------------------------------------------------------------------- output builders


def _claim(**fields) -> dict:
    base = {
        "status": None,
        "category": None,
        "amount": None,
        "currency": None,
        "expense_date": None,
        "merchant": None,
        "has_receipt": None,
        "description": "",
        "policy_result": None,
        "policy_reasons": [],
        "missing_fields": [],
        "clarification_question": None,
        "rejection_reason": None,
    }
    base.update(fields)
    return {key: base[key] for key in SCHEMA_KEY_ORDER}


def _rejected(reason: str) -> dict:
    """FR-034: every extracted field null, fixed neutral description."""
    return _claim(status="rejected", description=REJECTED_DESCRIPTIONS[reason],
                  rejection_reason=reason)


def _decide(extraction: dict, today: date) -> tuple[dict, int | None]:
    """Status decision after the rejection checks: needs_clarification or ok (FR-035 - FR-059).

    Returns the claim and the nights value used for the accommodation limit.
    """
    category = extraction["category"]
    amount = extraction["amount"]
    if amount is not None and amount <= 0:  # spec Edge Cases: 0 or negative = missing
        amount = None
    code = extraction["currency_code"]
    unsupported_code = code if code is not None and code not in SUPPORTED_CURRENCIES else None
    expense_date = _parse_date(extraction["expense_date"])
    future_date = expense_date if expense_date is not None and expense_date > today else None
    if future_date is not None:  # FR-042
        expense_date = None
    multiple = extraction["multiple_expenses"]
    nights = extraction["nights"] if category == "accommodation" else None

    if multiple:  # FR-043
        amount = None
        category = None
        nights = None
    if unsupported_code is not None:  # FR-044
        amount = None

    missing = {
        "amount": amount is None,
        "category": category is None,
        "expense_date": expense_date is None,
    }
    missing_fields = [name for name in FIELD_ORDER if missing[name]]

    currency_defaulted = code is None
    if amount is None or unsupported_code is not None:
        currency = None
    else:
        currency = code if code is not None else "SAR"  # FR-024 default

    common = {
        "category": category,
        "amount": amount,
        "currency": currency,
        "expense_date": expense_date.isoformat() if expense_date is not None else None,
        "merchant": extraction["merchant"],
        "has_receipt": extraction["has_receipt"],
        "description": extraction["description"],
    }

    if missing_fields:
        if multiple:
            question = MULTIPLE_EXPENSES_QUESTION
        else:
            sentences: list[str] = []
            covered: set[str] = set()
            if unsupported_code is not None:
                sentences.append(f"Currency {unsupported_code} is not supported. "
                                 "Please provide the amount in SAR, USD or EUR.")
                covered.add("amount")
            if future_date is not None:
                sentences.append(f"The expense date {future_date.isoformat()} is after today "
                                 f"({today.isoformat()}). Please provide the date the expense "
                                 "occurred.")
                covered.add("expense_date")
            remaining = [FIELD_NAMES[f] for f in missing_fields if f not in covered]
            if remaining:
                sentences.append(f"Please provide the missing {_join_names(remaining)} "
                                 "for this expense.")
            question = " ".join(sentences)
        claim = _claim(status="needs_clarification", missing_fields=missing_fields,
                       clarification_question=question, **common)
        return claim, nights

    decision = policy.evaluate(
        category=category,
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        has_receipt=extraction["has_receipt"],
        nights=nights,
        today=today,
        currency_defaulted=currency_defaulted,
    )
    claim = _claim(status="ok", policy_result=decision.result,
                   policy_reasons=list(decision.reasons), **common)
    return claim, nights


# --------------------------------------------------------------------------- final checks


def _finalise(claim: dict) -> dict:
    """Truncate, sanitise and mask every free-text field, then mask every string (FR-071)."""
    out = dict(claim)
    if out["merchant"] is not None:
        out["merchant"] = _clean_text(out["merchant"], MERCHANT_MAX)
    out["description"] = _clean_text(out["description"] or "", DESCRIPTION_MAX)
    if out["clarification_question"] is not None:
        out["clarification_question"] = _clean_text(out["clarification_question"])
    out["policy_reasons"] = [_clean_text(reason) for reason in out["policy_reasons"]]
    return mask_output(out)


def _invariant_violations(out: dict, today: date, nights: int | None) -> list[str]:
    """INV-1 - INV-7 (FR-060 - FR-066). The harness has its own, independent implementation."""
    violations: list[str] = []
    status = out["status"]
    if status == "ok" and any(
        out[key] is None
        for key in ("amount", "currency", "category", "expense_date", "policy_result")
    ):
        violations.append("INV-1")
    if status == "needs_clarification" and (
        not out["missing_fields"]
        or out["clarification_question"] is None
        or out["policy_result"] is not None
    ):
        violations.append("INV-2")
    if status == "rejected" and (
        out["rejection_reason"] is None or out["policy_result"] is not None
    ):
        violations.append("INV-3")
    category = out["category"]
    if out["currency"] == "SAR" and out["amount"] is not None and category in policy.LIMITS_SAR:
        limit = policy.LIMITS_SAR[category]
        if category == "accommodation":
            limit *= nights if nights and nights >= 1 else 1
        if out["amount"] > limit and out["policy_result"] != "needs_manager_approval":
            violations.append("INV-4")
    if out["expense_date"] is not None and date.fromisoformat(out["expense_date"]) > today:
        violations.append("INV-5")
    strings: list[str] = []
    for value in out.values():
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, list):
            strings.extend(item for item in value if isinstance(item, str))
    if any(find_unmasked_card_numbers(text) for text in strings):
        violations.append("INV-6")
    free_text = [out["description"], out["merchant"], out["clarification_question"],
                 *out["policy_reasons"]]
    if any(text and _FORBIDDEN_WORD_RE.search(text) for text in free_text):
        violations.append("INV-7")
    return violations


def _verified(claim: dict, today: date, nights: int | None) -> dict:
    out = _finalise(claim)
    if list(out) != list(SCHEMA_KEY_ORDER) or not _CLAIM_VALIDATOR.is_valid(out):
        raise InternalError("schema")
    if _invariant_violations(out, today, nights):
        raise InternalError("invariants")
    return out


# --------------------------------------------------------------------------- entry point


def validate_input(text: str) -> str:
    if not isinstance(text, str):
        raise UsageError("text must be a string")
    stripped = text.strip()
    if not stripped:
        raise UsageError("text is empty")
    if len(stripped) > config.MAX_INPUT_CHARS:
        raise UsageError(f"text is longer than {config.MAX_INPUT_CHARS} characters")
    return stripped


def assess(text: str, today: date, client) -> dict:
    """Assess one free-text expense against `today`; returns the 13-key claim dict.

    Raises `UsageError` for invalid input (no model call), lets `ModelError` propagate, and
    raises `InternalError` if the final output fails the schema or an invariant.
    """
    masked = mask_card_numbers(validate_input(text))  # FR-070

    # Deterministic guardrails: no model call (FR-030 steps 1-2, FR-031, FR-033).
    if _INJECTION_RE.search(masked):
        return _verified(_rejected("prompt_injection"), today, None)
    if _PROHIBITED_RE.search(masked):
        return _verified(_rejected("prohibited_item"), today, None)

    extraction = extractor.extract(client, masked, today)

    # Model signals in FR-030 order (steps 3-5).
    if extraction["prompt_injection"]:
        return _verified(_rejected("prompt_injection"), today, None)
    if not extraction["is_expense_request"]:
        return _verified(_rejected("out_of_scope"), today, None)
    if extraction["prohibited_item"]:
        return _verified(_rejected("prohibited_item"), today, None)

    claim, nights = _decide(extraction, today)
    return _verified(claim, today, nights)
