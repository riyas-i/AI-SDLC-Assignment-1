"""Evaluation dataset integrity (T012; FR-100, FR-101, FR-107, FR-108, Constitution VII, IX)."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "dataset.json"

# Cases approved by the requester (T009, spec Revision 3). Cases must never be deleted (FR-107).
APPROVED_IDS = {
    "S-01", "S-02", "S-03", "S-04", "S-05", "S-06",
    "P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07", "P-08", "P-09",
    "C-01", "C-02", "C-03", "C-04",
    "G-01", "G-02", "G-03", "G-04", "G-05", "G-06",
}  # fmt: skip

TAGS = {"guardrail", "policy_limit", "clarification", "standard"}
KINDS = {"normal", "boundary", "ambiguous", "missing_info", "malformed", "policy_limit",
         "adversarial"}
EXPECTED_KEYS = {"status", "rejection_reason", "policy_result", "missing_fields", "category",
                 "amount", "expense_date", "nights", "description_keywords"}
CARD_RUN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
TEST_CARD = "4111111111111111"


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cases(doc) -> list[dict]:
    return doc["cases"]


def test_dataset_is_versioned(doc):
    assert doc["spec_version"].startswith("Revision ")
    date.fromisoformat(doc["revised"])
    date.fromisoformat(doc["today_default"])


def test_ids_are_unique(cases):
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_minimum_case_count(cases):
    assert len(cases) >= 24  # FR-100


def test_no_approved_case_was_deleted(cases):
    assert APPROVED_IDS <= {c["id"] for c in cases}  # FR-107


def test_tag_minimums(cases):
    for case in cases:
        assert case["tags"], case["id"]
        assert set(case["tags"]) <= TAGS, case["id"]
    counts = Counter(t for c in cases for t in c["tags"])
    assert counts["guardrail"] >= 4
    assert counts["policy_limit"] >= 4
    assert counts["clarification"] >= 2
    assert counts["standard"] >= 2


def test_every_kind_present(cases):
    assert {c["kind"] for c in cases} == KINDS


def test_guardrail_reason_coverage(cases):
    reasons = {c["expected"]["rejection_reason"] for c in cases if "guardrail" in c["tags"]}
    assert {"prompt_injection", "out_of_scope", "prohibited_item"} <= reasons


def test_every_expected_key_present(cases):
    for case in cases:
        assert set(case["expected"]) == EXPECTED_KEYS, case["id"]
        assert {"id", "kind", "tags", "input", "today", "expected", "spec_ref"} <= set(case)


def test_dates_are_valid_iso(cases):
    for case in cases:
        today = date.fromisoformat(case["today"])
        expense_date = case["expected"]["expense_date"]
        if expense_date is not None:
            assert date.fromisoformat(expense_date) <= today, case["id"]


def test_expected_values_are_consistent(cases):
    for case in cases:
        e = case["expected"]
        assert e["status"] in {"ok", "needs_clarification", "rejected"}, case["id"]
        if e["status"] == "ok":
            assert e["policy_result"] in {"within_policy", "needs_manager_approval"}, case["id"]
            assert e["rejection_reason"] is None and e["missing_fields"] == [], case["id"]
        else:
            assert e["policy_result"] is None, case["id"]
        if e["status"] == "needs_clarification":
            assert e["missing_fields"], case["id"]
        if e["status"] == "rejected":
            assert e["rejection_reason"] is not None, case["id"]
            for key in ("category", "amount", "expense_date", "nights"):
                assert e[key] is None, (case["id"], key)


def test_only_the_test_card_number_is_used(cases):
    card_cases = []
    for case in cases:
        for run in CARD_RUN.findall(case["input"]):
            assert re.sub(r"[ -]", "", run) == TEST_CARD, case["id"]
            card_cases.append(case["id"])
    assert card_cases, "FR-101 requires at least one card-masking case"


def test_pre_approved_case_expects_ok(cases):
    pre = [c for c in cases if "pre-approved" in c["input"].lower()]
    assert pre, "FR-101 requires the innocent 'pre-approved' case"
    for case in pre:
        assert case["expected"]["status"] == "ok", case["id"]
        assert "guardrail" in case["tags"], case["id"]
