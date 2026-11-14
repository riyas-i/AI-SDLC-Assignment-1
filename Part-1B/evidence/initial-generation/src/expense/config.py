"""Single configuration location (FR-090, Constitution V).

The API key is only ever read from the `GEMINI_API_KEY` environment variable (optionally populated
by python-dotenv from the project's `.env`). Nothing in this module logs or prints it (FR-085).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_NAME = "gemini-2.5-flash"
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 30
RETRY_BACKOFF_SECONDS = (1, 2, 4)
CALL_DELAY_SECONDS = 7.0
MAX_INPUT_CHARS = 1000

PROMPT_PATH = PROJECT_ROOT / "prompts" / "system.md"
CLAIM_SCHEMA_PATH = PROJECT_ROOT / "contracts" / "claim.schema.json"
EXTRACTION_SCHEMA_PATH = PROJECT_ROOT / "contracts" / "extraction.schema.json"

API_KEY_ENV = "GEMINI_API_KEY"


def get_api_key() -> str | None:
    """Return the API key from the environment, or None if it is not set (FR-084).

    `load_dotenv(override=False)` never replaces a variable that is already set.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return os.environ.get(API_KEY_ENV) or None
