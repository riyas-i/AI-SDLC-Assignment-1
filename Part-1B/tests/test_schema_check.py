"""Schema evaluator (T014; FR-010, FR-102, AC-078)."""

from __future__ import annotations

import pytest

import schema_check

CASE = {"id": "T-1", "today": "2026-11-14", "expected": {}}


def test_valid_output_passes(sample_outputs):
    for ac_id, output in sample_outputs.items():
        result = schema_check.check(CASE, output)
        assert result.name == "schema"
        assert result.passed, (ac_id, result.details)
        assert result.details == []


def _mutations():
    def missing_key(o):
        del o["merchant"]

    def extra_key(o):
        o["approved_by"] = "manager"

    def zero_amount(o):
        o["amount"] = 0

    def gbp(o):
        o["currency"] = "GBP"

    def long_description(o):
        o["description"] = "d" * 121

    def long_merchant(o):
        o["merchant"] = "m" * 81

    def bad_status(o):
        o["status"] = "approved"

    return {
        "missing key": missing_key,
        "extra key": extra_key,
        "amount 0": zero_amount,
        "currency GBP": gbp,
        "description 121 chars": long_description,
        "merchant 81 chars": long_merchant,
        "unknown status": bad_status,
    }


@pytest.mark.parametrize("label", list(_mutations()))
def test_invalid_output_fails_with_details(sample_outputs, label):
    output = sample_outputs["AC-001"]
    _mutations()[label](output)
    result = schema_check.check(CASE, output)
    assert not result.passed, label
    assert result.details and all(isinstance(d, str) for d in result.details)


def test_boundary_lengths_pass(sample_outputs):
    output = sample_outputs["AC-001"]
    output["description"] = "d" * 120
    output["merchant"] = "m" * 80
    assert schema_check.check(CASE, output).passed


def test_all_errors_are_collected(sample_outputs):
    output = sample_outputs["AC-001"]
    output["currency"] = "GBP"
    output["description"] = "d" * 121
    assert len(schema_check.check(CASE, output).details) >= 2


def test_no_output_fails():
    result = schema_check.check(CASE, None)
    assert result.name == "schema"
    assert not result.passed
    assert result.details
