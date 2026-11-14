"""Output and extraction contracts (T013; FR-010, FR-011, FR-020, AC-005)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from conftest import SCHEMA_KEY_ORDER

ROOT = Path(__file__).resolve().parents[1]
SPEC_CONTRACTS = ROOT / "specs" / "001-expense-claim-assistant" / "contracts"
REPO_CONTRACTS = ROOT / "contracts"
SCHEMAS = ["claim.schema.json", "extraction.schema.json"]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SCHEMAS)
def test_repo_copy_equals_spec_copy(name):
    assert (REPO_CONTRACTS / name).read_bytes() == (SPEC_CONTRACTS / name).read_bytes()


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_is_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(_load(REPO_CONTRACTS / name))


def test_claim_schema_requires_exactly_13_keys_in_order():
    schema = _load(REPO_CONTRACTS / "claim.schema.json")
    assert schema["required"] == SCHEMA_KEY_ORDER
    assert list(schema["properties"]) == SCHEMA_KEY_ORDER
    assert schema["additionalProperties"] is False


def test_extraction_schema_has_no_decision_fields():
    schema = _load(REPO_CONTRACTS / "extraction.schema.json")
    for forbidden in ("status", "policy_result", "policy_reasons"):  # FR-021
        assert forbidden not in schema["properties"]
    assert schema["additionalProperties"] is False


def test_sample_outputs_validate(sample_outputs):
    validator = Draft202012Validator(_load(REPO_CONTRACTS / "claim.schema.json"))
    for ac_id, output in sample_outputs.items():
        errors = [e.message for e in validator.iter_errors(output)]
        assert errors == [], (ac_id, errors)
        assert list(output) == SCHEMA_KEY_ORDER, ac_id


def test_fourteenth_key_is_rejected(sample_outputs):
    validator = Draft202012Validator(_load(REPO_CONTRACTS / "claim.schema.json"))
    output = sample_outputs["AC-001"]
    output["approved"] = True
    assert not validator.is_valid(output)


def test_missing_key_is_rejected(sample_outputs):
    validator = Draft202012Validator(_load(REPO_CONTRACTS / "claim.schema.json"))
    output = sample_outputs["AC-001"]
    del output["rejection_reason"]
    assert not validator.is_valid(output)
