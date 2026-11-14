"""Gemini client: retries and error classification (T028; FR-080 - FR-085, AC-060 - AC-069).

The SDK's `genai.Client` is replaced by a fake; `time.sleep` is patched to record the waits.
Exceptions are the real classes the SDK raises (`google.genai.errors`, `httpx2`), per research R2.
"""

from __future__ import annotations

import json
import time

import httpx2
import pytest
from expense.llm_client import AttemptRecord, GeminiClient, ModelError
from google.genai import errors

from conftest import FAKE_KEY
from expense import config, llm_client

SYSTEM = "SYSTEM PROMPT"
USER = "Today: 2026-11-14\n<expense>\ntaxi 85 SAR yesterday\n</expense>"

VALID_EXTRACTION = {
    "is_expense_request": True,
    "prompt_injection": False,
    "prohibited_item": False,
    "multiple_expenses": False,
    "category": "transport",
    "amount": 85,
    "currency_code": "SAR",
    "expense_date": "2026-11-13",
    "merchant": None,
    "has_receipt": True,
    "nights": None,
    "description": "Taxi from airport to client office",
}


def timeout_error():
    return httpx2.ReadTimeout("read timed out")


def network_error():
    return httpx2.ConnectError("connection refused")


def api_error(code: int, status: str, message: str = "error"):
    body = {"error": {"code": code, "message": message, "status": status}}
    if code >= 500:
        return errors.ServerError(code, body)
    return errors.ClientError(code, body)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def generate_content(self, *args, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return FakeResponse(item)


@pytest.fixture
def waits(monkeypatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(time, "sleep", recorded.append)
    return recorded


@pytest.fixture
def sdk(monkeypatch):
    """`sdk(script)` installs a fake genai.Client; returns (models, init_kwargs)."""

    def install(script):
        models = FakeModels(script)
        init: dict = {}

        class FakeGenaiClient:
            def __init__(self, *args, **kwargs):
                init.update(kwargs)
                self.models = models

        monkeypatch.setattr(llm_client.genai, "Client", FakeGenaiClient)
        return models, init

    return install


def _call(script, sdk):
    models, init = sdk(script)
    client = GeminiClient(FAKE_KEY)
    return client, models, init


def _outcomes(attempts) -> list[str]:
    return [a.outcome for a in attempts]


# --------------------------------------------------------------------------- configuration


def test_config_values():
    assert config.MODEL_NAME == "gemini-3.5-flash"  # spec Revision 4
    assert config.TEMPERATURE == 0.0
    assert config.TIMEOUT_SECONDS == 30
    assert tuple(config.RETRY_BACKOFF_SECONDS) == (1, 2, 4)
    assert config.CALL_DELAY_SECONDS == 7.0
    assert config.MAX_INPUT_CHARS == 1000


def test_get_api_key_reads_environment(monkeypatch):
    assert config.get_api_key() is None
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    assert config.get_api_key() == FAKE_KEY


# --------------------------------------------------------------------------- success


def test_first_attempt_success(sdk, waits, capsys):
    client, models, init = _call([json.dumps(VALID_EXTRACTION)], sdk)
    assert client.generate_json(SYSTEM, USER) == VALID_EXTRACTION
    assert waits == []
    assert capsys.readouterr().err == ""
    assert _outcomes(client.last_attempts) == ["ok"]
    assert client.last_attempts[0].attempt == 1
    assert isinstance(client.last_attempts[0].elapsed_ms, int | float)

    assert init["api_key"] == FAKE_KEY
    assert init["http_options"].timeout == 30000
    assert init["http_options"].retry_options.attempts == 1  # SDK retries disabled (R2)

    call = models.calls[0]
    assert call["model"] == "gemini-3.5-flash"  # spec Revision 4
    assert USER in str(call["contents"])
    cfg = call["config"]
    assert cfg.system_instruction == SYSTEM
    assert cfg.temperature == 0.0
    assert cfg.response_mime_type == "application/json"


def test_ac067_network_then_success(sdk, waits, capsys):
    client, models, _ = _call([network_error(), json.dumps(VALID_EXTRACTION)], sdk)
    assert client.generate_json(SYSTEM, USER) == VALID_EXTRACTION
    assert _outcomes(client.last_attempts) == ["network", "ok"]
    assert [a.attempt for a in client.last_attempts] == [1, 2]
    assert waits == [1]
    assert capsys.readouterr().err.splitlines() == ["retry 1/3: network"]


# --------------------------------------------------------------------------- retried failures


@pytest.mark.parametrize(("make_error", "error_type", "status"), [
    (timeout_error, "timeout", None),                                       # AC-060
    (lambda: api_error(429, "RESOURCE_EXHAUSTED"), "quota", 429),           # AC-063
    (network_error, "network", None),                                       # AC-064
    (lambda: api_error(503, "UNAVAILABLE"), "server", 503),                 # AC-068
])
def test_retried_four_times_then_model_error(sdk, waits, capsys, make_error, error_type,
                                             status):
    client, models, _ = _call([make_error() for _ in range(4)], sdk)
    with pytest.raises(ModelError) as info:
        client.generate_json(SYSTEM, USER)
    exc = info.value
    assert exc.error_type == error_type
    assert exc.http_status == status
    assert str(exc) == f"model_error: {error_type}"
    assert _outcomes(exc.attempts) == [error_type] * 4
    assert [a.attempt for a in exc.attempts] == [1, 2, 3, 4]
    assert len(models.calls) == 4
    assert waits == [1, 2, 4]
    assert capsys.readouterr().err.splitlines() == [
        f"retry {n}/3: {error_type}" for n in (1, 2, 3)
    ]
    assert _outcomes(client.last_attempts) == [error_type] * 4


def test_last_failure_sub_type_is_reported(sdk, waits):
    script = [network_error(), timeout_error(), api_error(503, "UNAVAILABLE"),
              api_error(429, "RESOURCE_EXHAUSTED")]
    client, _, _ = _call(script, sdk)
    with pytest.raises(ModelError) as info:
        client.generate_json(SYSTEM, USER)
    assert info.value.error_type == "quota"
    assert _outcomes(info.value.attempts) == ["network", "timeout", "server", "quota"]


# --------------------------------------------------------------------------- not retried


@pytest.mark.parametrize("text", ["this is not json", "", None, "[1, 2]"])
def test_ac061_invalid_json_not_retried(sdk, waits, text):
    client, models, _ = _call([text], sdk)
    with pytest.raises(ModelError) as info:
        client.generate_json(SYSTEM, USER)
    assert info.value.error_type == "invalid_response"
    assert len(models.calls) == 1
    assert waits == []
    assert _outcomes(info.value.attempts) == ["invalid_response"]


@pytest.mark.parametrize("payload", [
    {"amount": 5},                                                  # missing keys
    {**VALID_EXTRACTION, "status": "ok"},                           # FR-021 decision field
    {**VALID_EXTRACTION, "currency_code": "riyal"},                 # bad pattern
    {**VALID_EXTRACTION, "nights": 0},                              # nights >= 1
    {**VALID_EXTRACTION, "category": "alcohol"},                    # unknown enum
])
def test_ac062_schema_invalid_json(sdk, waits, payload):
    client, models, _ = _call([json.dumps(payload)], sdk)
    with pytest.raises(ModelError) as info:
        client.generate_json(SYSTEM, USER)
    assert info.value.error_type == "invalid_response"
    assert len(models.calls) == 1


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_ac069_client_error_not_retried(sdk, waits, capsys, code):
    message = f"API key {FAKE_KEY} not valid. Please pass a valid API key."
    client, models, _ = _call([api_error(code, "PERMISSION_DENIED", message)], sdk)
    with pytest.raises(ModelError) as info:
        client.generate_json(SYSTEM, USER)
    exc = info.value
    assert exc.error_type == "api_error"
    assert exc.http_status == code
    assert len(models.calls) == 1
    assert waits == []
    # FR-085 / AC-066: the key never appears, even when the API echoes it back.
    err = capsys.readouterr().err
    for text in (str(exc), repr(exc), err, repr(exc.attempts)):
        assert FAKE_KEY not in text


def test_key_not_in_client_repr(sdk):
    client, _, _ = _call([], sdk)
    assert FAKE_KEY not in repr(client)
    assert FAKE_KEY not in str(getattr(client, "__dict__", {}))


def test_model_error_constructor_defaults():
    exc = ModelError("timeout")
    assert exc.error_type == "timeout"
    assert list(exc.attempts) == []
    assert exc.http_status is None
    assert str(exc) == "model_error: timeout"


def test_attempt_record_fields():
    record = AttemptRecord(attempt=2, outcome="ok", elapsed_ms=12)
    assert (record.attempt, record.outcome, record.elapsed_ms) == (2, "ok", 12)
