"""Gemini client with our own retry loop and error classification (FR-080 - FR-085, research R2).

SDK-level retries are disabled so every attempt is visible and recorded (Constitution VI).
The API key is passed straight to `genai.Client` and never stored on this object, logged or put
into an error message (FR-085). No API message text is kept: it can echo the request or the key.
"""

from __future__ import annotations

import importlib
import json
import re
import sys
import time
from dataclasses import dataclass

from google import genai
from google.genai import errors, types
from jsonschema import Draft202012Validator

from expense import config

RETRIED = frozenset({"timeout", "network", "quota", "server"})
ERROR_TYPES = frozenset(RETRIED | {"api_error", "invalid_response"})


def _transport_classes() -> tuple[tuple[type, ...], tuple[type, ...]]:
    """Timeout and transport exception classes of whichever of httpx/httpx2 is importable."""
    timeouts: list[type] = []
    transports: list[type] = []
    for name in ("httpx", "httpx2"):
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        timeouts.append(module.TimeoutException)
        transports.append(module.TransportError)
    timeouts.append(TimeoutError)
    transports.append(ConnectionError)
    return tuple(timeouts), tuple(transports)


_TIMEOUT_ERRORS, _TRANSPORT_ERRORS = _transport_classes()


@dataclass(frozen=True)
class AttemptRecord:
    attempt: int
    outcome: str
    elapsed_ms: int


@dataclass(frozen=True)
class ApiErrorAttemptRecord(AttemptRecord):
    """An attempt the API answered with an HTTP error: adds the HTTP status code and Gemini's
    short status word (e.g. `INVALID_ARGUMENT`). The API's message text is never kept: it can
    echo the request or the key (FR-085)."""

    http_status: int | None = None
    api_status: str | None = None


_STATUS_WORD = re.compile(r"[A-Z][A-Z_]{0,63}")


def _status_word(value: object) -> str | None:
    """Gemini's status word only if it is a bare upper-case token; anything else is dropped."""
    if isinstance(value, str) and _STATUS_WORD.fullmatch(value):
        return value
    return None


class ModelError(Exception):
    """A model-call failure. `str()` is only `model_error: <type>` (never API text or the key)."""

    def __init__(
        self,
        error_type: str,
        attempts: list[AttemptRecord] | None = None,
        http_status: int | None = None,
        api_status: str | None = None,
    ) -> None:
        super().__init__(error_type)
        self.error_type = error_type
        self.attempts: list[AttemptRecord] = list(attempts or [])
        self.http_status = http_status
        self.api_status = _status_word(api_status)

    def __str__(self) -> str:
        return f"model_error: {self.error_type}"

    def __repr__(self) -> str:
        return (f"ModelError(error_type={self.error_type!r}, http_status={self.http_status!r}, "
                f"api_status={self.api_status!r})")


class _AttemptFailure(Exception):
    def __init__(self, error_type: str, http_status: int | None = None,
                 api_status: str | None = None, from_api: bool = False) -> None:
        super().__init__(error_type)
        self.error_type = error_type
        self.http_status = http_status
        self.api_status = _status_word(api_status)
        self.from_api = from_api

    def record(self, attempt: int, elapsed_ms: int) -> AttemptRecord:
        if self.from_api:
            return ApiErrorAttemptRecord(attempt, self.error_type, elapsed_ms,
                                         self.http_status, self.api_status)
        return AttemptRecord(attempt, self.error_type, elapsed_ms)


def _load_extraction_schema() -> dict:
    return json.loads(config.EXTRACTION_SCHEMA_PATH.read_text(encoding="utf-8"))


_EXTRACTION_SCHEMA = _load_extraction_schema()
_EXTRACTION_VALIDATOR = Draft202012Validator(_EXTRACTION_SCHEMA)
# Schema sent to the API: the same contract without the meta keys.
_RESPONSE_SCHEMA = {k: v for k, v in _EXTRACTION_SCHEMA.items() if k not in ("$schema", "$id")}


def is_valid_extraction(data: object) -> bool:
    """True if `data` matches `contracts/extraction.schema.json` (FR-020)."""
    return isinstance(data, dict) and _EXTRACTION_VALIDATOR.is_valid(data)


def _validate_extraction(data: object) -> dict:
    if not is_valid_extraction(data):
        raise _AttemptFailure("invalid_response")
    return data  # type: ignore[return-value]


def _classify(exc: BaseException) -> _AttemptFailure | None:
    if isinstance(exc, _TIMEOUT_ERRORS):
        return _AttemptFailure("timeout")
    if isinstance(exc, _TRANSPORT_ERRORS):
        return _AttemptFailure("network")
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)
        status = code if isinstance(code, int) else None
        word = getattr(exc, "status", None)
        if status == 429:
            error_type = "quota"
        elif isinstance(exc, errors.ServerError) or (status is not None and status >= 500):
            error_type = "server"
        else:
            error_type = "api_error"
        return _AttemptFailure(error_type, status, word, from_api=True)
    return None


class GeminiClient:
    """`generate_json(system, user) -> dict` against `config.MODEL_NAME` in JSON mode."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=config.TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self.last_attempts: list[AttemptRecord] = []

    def __repr__(self) -> str:
        return f"GeminiClient(model={config.MODEL_NAME!r})"

    def _attempt(self, system: str, user: str) -> dict:
        try:
            response = self._client.models.generate_content(
                model=config.MODEL_NAME,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=config.TEMPERATURE,
                    response_mime_type="application/json",
                    response_json_schema=_RESPONSE_SCHEMA,
                ),
            )
        except Exception as exc:
            failure = _classify(exc)
            if failure is None:
                raise
            raise failure from None

        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise _AttemptFailure("invalid_response")
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            raise _AttemptFailure("invalid_response") from None
        return _validate_extraction(data)

    def generate_json(self, system: str, user: str) -> dict:
        """Call the model with up to 4 attempts (backoff 1, 2, 4 s) for retryable failures."""
        attempts: list[AttemptRecord] = []
        self.last_attempts = attempts
        backoff = list(config.RETRY_BACKOFF_SECONDS)
        max_attempts = len(backoff) + 1

        for number in range(1, max_attempts + 1):
            start = time.perf_counter()
            try:
                result = self._attempt(system, user)
            except _AttemptFailure as failure:
                elapsed = round((time.perf_counter() - start) * 1000)
                attempts.append(failure.record(number, elapsed))
                if failure.error_type in RETRIED and number < max_attempts:
                    print(f"retry {number}/{len(backoff)}: {failure.error_type}",
                          file=sys.stderr)
                    time.sleep(backoff[number - 1])
                    continue
                raise ModelError(failure.error_type, list(attempts),
                                 failure.http_status, failure.api_status) from None
            elapsed = round((time.perf_counter() - start) * 1000)
            attempts.append(AttemptRecord(number, "ok", elapsed))
            return result

        raise ModelError("network", list(attempts))  # pragma: no cover - loop always returns
