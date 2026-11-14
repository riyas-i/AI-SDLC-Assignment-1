"""Shared fixtures for the offline test suite (T010).

No test in this suite may call the Gemini API or read `.env` (FR-109, CLAUDE.md). Two autouse
fixtures enforce that: outbound socket connections fail, and python-dotenv loading is disabled
with `GEMINI_API_KEY` removed from the environment unless a test opts in via `fake_key`.
"""

from __future__ import annotations

import copy
import socket
from collections import deque
from datetime import date

import pytest

FAKE_KEY = "test-key-DO-NOT-LEAK-123"

SCHEMA_KEY_ORDER = [
    "status",
    "category",
    "amount",
    "currency",
    "expense_date",
    "merchant",
    "has_receipt",
    "description",
    "policy_result",
    "policy_reasons",
    "missing_fields",
    "clarification_question",
    "rejection_reason",
]

REJECTED_DESCRIPTIONS = {
    "prompt_injection": "Request contains instructions to change the assistant's rules",
    "out_of_scope": "Request is not an expense claim",
    "prohibited_item": "Expense is a prohibited item under company policy",
}


# --------------------------------------------------------------------------- safety (autouse)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if anything tries to open a network connection (FR-109)."""

    def _blocked(*args, **kwargs):
        raise RuntimeError("network access is not allowed in unit tests (FR-109)")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def _no_real_key(monkeypatch):
    """Never load `.env` and never expose a real key to a test (CLAUDE.md, FR-085)."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _no_dotenv(*args, **kwargs):
        return False

    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", _no_dotenv)
    try:
        import dotenv.main

        monkeypatch.setattr(dotenv.main, "load_dotenv", _no_dotenv)
    except ImportError:  # pragma: no cover - layout differs between versions
        pass
    try:  # expense.config may bind load_dotenv at import time (exists from Phase 4)
        import expense.config as expense_config
    except ImportError:
        expense_config = None
    if expense_config is not None and hasattr(expense_config, "load_dotenv"):
        monkeypatch.setattr(expense_config, "load_dotenv", _no_dotenv)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def fake_key(monkeypatch) -> str:
    """Set a recognisable fake key so tests can assert it never leaks (FR-085)."""
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    return FAKE_KEY


@pytest.fixture
def today() -> date:
    return date(2026, 11, 14)


def _claim(**overrides) -> dict:
    base = {
        "status": "ok",
        "category": None,
        "amount": None,
        "currency": None,
        "expense_date": None,
        "merchant": None,
        "has_receipt": None,
        "description": "",
        "policy_result": None,
        "policy_reasons": [],
        "missing_fields": [],
        "clarification_question": None,
        "rejection_reason": None,
    }
    unknown = set(overrides) - set(base)
    assert not unknown, f"unknown claim keys {unknown}"
    base.update(overrides)
    return {k: base[k] for k in SCHEMA_KEY_ORDER}


_SAMPLE_OUTPUTS = {
    # AC-001: complete valid transport claim.
    "AC-001": _claim(
        status="ok",
        category="transport",
        amount=85,
        currency="SAR",
        expense_date="2026-11-13",
        merchant=None,
        has_receipt=True,
        description="Taxi from airport to client office",
        policy_result="within_policy",
    ),
    # AC-011: meals 1 SAR over the limit.
    "AC-011": _claim(
        status="ok",
        category="meals",
        amount=151,
        currency="SAR",
        expense_date="2026-11-13",
        merchant="Desert Bites Cafe",
        has_receipt=True,
        description="Team dinner at Desert Bites Cafe",
        policy_result="needs_manager_approval",
        policy_reasons=["Amount 151 SAR exceeds the meals limit of 150 SAR"],
    ),
    # AC-030: amount missing.
    "AC-030": _claim(
        status="needs_clarification",
        category="transport",
        amount=None,
        currency=None,
        expense_date="2026-11-13",
        has_receipt=True,
        description="Taxi to the office",
        missing_fields=["amount"],
        clarification_question="Please provide the missing amount for this expense.",
    ),
    # AC-034: future date.
    "AC-034": _claim(
        status="needs_clarification",
        category="transport",
        amount=50,
        currency="SAR",
        expense_date=None,
        has_receipt=True,
        description="Taxi",
        missing_fields=["expense_date"],
        clarification_question=(
            "The expense date 2026-11-15 is after today (2026-11-14). "
            "Please provide the date the expense occurred."
        ),
    ),
    # AC-040: prompt injection.
    "AC-040": _claim(
        status="rejected",
        description=REJECTED_DESCRIPTIONS["prompt_injection"],
        rejection_reason="prompt_injection",
    ),
    # AC-048: card number in the input, masked everywhere.
    "AC-048": _claim(
        status="ok",
        category="meals",
        amount=70,
        currency="SAR",
        expense_date="2026-11-13",
        merchant="Desert Bites Cafe",
        has_receipt=True,
        description="Lunch at Desert Bites Cafe",
        policy_result="within_policy",
    ),
}


@pytest.fixture
def sample_outputs() -> dict[str, dict]:
    """Fixed, contract-conforming claim dicts keyed by AC id (fresh deep copy per test)."""
    return copy.deepcopy(_SAMPLE_OUTPUTS)


@pytest.fixture
def make_claim():
    """Factory for a 13-key claim dict in schema order."""
    return _claim


class StubClient:
    """Stand-in for GeminiClient: `generate_json(system, user) -> dict`.

    Queue dicts (returned) or exceptions (raised). Every call is recorded; a call with an
    empty queue fails the test, which is how tests prove "zero model calls".
    """

    def __init__(self, *responses):
        self._queue: deque = deque(responses)
        self.calls: list[tuple[str, str]] = []
        self.last_attempts: list = []

    def queue(self, *responses) -> StubClient:
        self._queue.extend(responses)
        return self

    def generate_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        if not self._queue:
            raise AssertionError("unexpected model call: StubClient queue is empty")
        item = self._queue.popleft()
        if isinstance(item, BaseException):
            raise item
        return copy.deepcopy(item)

    @property
    def user_texts(self) -> list[str]:
        return [user for _, user in self.calls]


@pytest.fixture
def stub_client():
    """Factory: `stub_client(resp1, resp2, ...)` -> StubClient."""
    return StubClient
