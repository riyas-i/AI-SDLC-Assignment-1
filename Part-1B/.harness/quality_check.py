"""Quality evaluator (T021, FR-102, FR-103, AC-077).

score = mean of four equally weighted components:
  category exact (1/0), amount exact (numeric equality, 1/0), expense_date exact (1/0),
  description fidelity (fraction of expected keywords found, case-insensitive; 1.0 if none).
An expected null matches only an actual null. passed = score >= CASE_QUALITY_MIN (verdict.py).
"""

from __future__ import annotations

from check_result import CheckResult
from verdict import CASE_QUALITY_MIN


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _same(expected, actual) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if _is_number(expected) and _is_number(actual):
        return float(expected) == float(actual)
    return expected == actual


def check(case: dict, output: dict | None) -> CheckResult:
    if output is None:
        return CheckResult("quality", False, score=0.0, details=["no output produced"])

    expected = case["expected"]
    details: list[str] = []
    components: list[float] = []

    for key in ("category", "amount", "expense_date"):
        match = _same(expected[key], output.get(key))
        components.append(1.0 if match else 0.0)
        if not match:
            details.append(f"{key}: expected {expected[key]!r}, got {output.get(key)!r}")

    keywords = expected.get("description_keywords") or []
    if keywords:
        description = (output.get("description") or "").lower()
        missing = [k for k in keywords if k.lower() not in description]
        components.append((len(keywords) - len(missing)) / len(keywords))
        if missing:
            details.append(f"description: missing keywords {missing}")
    else:
        components.append(1.0)

    score = round(sum(components) / len(components), 4)
    return CheckResult("quality", score >= CASE_QUALITY_MIN, score=score, details=details)
