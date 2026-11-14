"""Command-line interface: `expense "<text>" [--today YYYY-MM-DD]` (contracts/cli.md).

Exit codes: 0 assessment printed, 1 usage error or missing key, 2 model_error, 3 internal_error.
The API key value is never printed (FR-085).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

from expense import config, service
from expense.llm_client import GeminiClient, ModelError

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_MODEL_ERROR = 2
EXIT_INTERNAL_ERROR = 3

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class _ArgumentError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """Report argument problems as `usage error:` with exit code 1 instead of argparse's 2."""

    def error(self, message: str):  # type: ignore[override]
        raise _ArgumentError(message)


def build_client(api_key: str) -> GeminiClient:
    """The single place a real model client is created (tests patch this)."""
    return GeminiClient(api_key)


def _parse_today(value: str | None) -> date:
    if value is None:
        return date.today()
    if not _ISO_DATE.match(value):
        raise _ArgumentError(f"--today must be an ISO date YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _ArgumentError(f"--today is not a valid date: {value!r}") from None


def _build_parser() -> _Parser:
    parser = _Parser(prog="expense", description="Assess one free-text expense claim.")
    parser.add_argument("text", help="the expense, in free text (max 1000 characters)")
    parser.add_argument("--today", default=None,
                        help="reference date YYYY-MM-DD (default: local date)")
    return parser


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):  # pragma: no cover - stream does not allow it
                pass


def main(argv: list[str] | None = None) -> int:
    _configure_streams()

    try:
        args = _build_parser().parse_args(argv)
        today = _parse_today(args.today)
    except _ArgumentError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    # FR-003: input checks happen before the key check and before any client exists.
    try:
        service.validate_input(args.text)
    except service.UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    api_key = config.get_api_key()
    if not api_key:  # FR-084 / AC-065: no client is built without a key
        print(f"{config.API_KEY_ENV} is not set", file=sys.stderr)
        return EXIT_USAGE

    client = build_client(api_key)
    del api_key

    try:
        result = service.assess(args.text, today, client)
    except service.UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ModelError as exc:
        print(f"model_error: {exc.error_type}", file=sys.stderr)
        return EXIT_MODEL_ERROR
    except service.InternalError as exc:
        print(f"internal_error: {exc.check}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR

    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
