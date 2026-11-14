"""Card-number masking (FR-065, FR-070, FR-071, research R8)."""

from __future__ import annotations

import re
from typing import Any

CARD_PATTERN = r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
_CARD_RE = re.compile(CARD_PATTERN)


def _mask_match(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "*" * (len(digits) - 4) + digits[-4:]


def mask_card_numbers(text: str) -> str:
    """Replace every 13-19 digit run (optional single space/hyphen separators) with
    `*` for each digit except the last four, separators removed."""
    return _CARD_RE.sub(_mask_match, text)


def find_unmasked_card_numbers(text: str) -> list[str]:
    """Return every card-number-like run still present in `text`."""
    return [m.group(0) for m in _CARD_RE.finditer(text)]


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_card_numbers(value)
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _mask_value(item) for key, item in value.items()}
    return value


def mask_output(obj: dict) -> dict:
    """Return a copy of the claim dict with every string value masked (key order kept)."""
    return {key: _mask_value(value) for key, value in obj.items()}
