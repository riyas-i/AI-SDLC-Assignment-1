"""Outcome evaluator: decision fields equal the expected ones (T019, FR-102, AC-080, AC-081).

Pure function, no I/O. Lists are compared with `==`, so `missing_fields` order matters (FR-041).
"""

from __future__ import annotations

from check_result import CheckResult

OUTCOME_FIELDS = ("status", "rejection_reason", "policy_result", "missing_fields")


def check(case: dict, output: dict | None) -> CheckResult:
    if output is None:
        return CheckResult("outcome", False, details=["no output produced"])
    expected = case["expected"]
    details = [
        f"{key}: expected {expected[key]!r}, got {output.get(key)!r}"
        for key in OUTCOME_FIELDS
        if output.get(key) != expected[key]
    ]
    return CheckResult("outcome", not details, details=details)
