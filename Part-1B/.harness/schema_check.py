"""Schema evaluator: output validates against contracts/claim.schema.json (T015, FR-102, AC-078).

Pure function, no network. The schema is read once at import time.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from check_result import CheckResult

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "contracts" / "claim.schema.json"
_VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def check(case: dict, output: dict | None) -> CheckResult:
    if output is None:
        return CheckResult("schema", False, details=["no output produced"])
    details = []
    for error in sorted(_VALIDATOR.iter_errors(output), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(p) for p in error.absolute_path) or "<root>"
        details.append(f"{location}: {error.message}")
    return CheckResult("schema", not details, details=details)
