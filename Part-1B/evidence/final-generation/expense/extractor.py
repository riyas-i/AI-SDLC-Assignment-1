"""Model extraction: prompt assembly, model call and validation (FR-020 - FR-023)."""

from __future__ import annotations

from datetime import date

from expense import config
from expense.llm_client import ModelError, is_valid_extraction


def load_system_prompt() -> str:
    """The system instruction is loaded at runtime from `prompts/system.md` (plan Design Notes)."""
    return config.PROMPT_PATH.read_text(encoding="utf-8")


def build_user_message(masked_text: str, today: date) -> str:
    return f"Today: {today.isoformat()}\n<expense>\n{masked_text}\n</expense>"


def _is_calendar_date(value: str | None) -> bool:
    if value is None:
        return True
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def extract(client, masked_text: str, today: date) -> dict:
    """Return the schema-validated extraction for `masked_text`.

    The extraction is validated again here (whatever client produced it), and an
    `expense_date` that is not a real calendar date is an invalid response. Failures raise
    `ModelError("invalid_response")`.
    """
    data = client.generate_json(load_system_prompt(), build_user_message(masked_text, today))
    attempts = list(getattr(client, "last_attempts", None) or [])
    if not is_valid_extraction(data) or not _is_calendar_date(data["expense_date"]):
        raise ModelError("invalid_response", attempts)
    return data
