"""Shared pytest fixtures and helpers for the Smart Todo CLI test suite.

Conventions (tasks.md, Phase 2):

- ``cli_env``: chdir into a fresh ``tmp_path`` so every test has its own ``tasks.json``.
  Every other fixture here depends on it, so using any of them isolates the test.
- ``run(*args)``: call ``todo.cli.main(list(args))`` in-process and return
  ``Result(code, out, err)``. ``out``/``err`` keep their trailing newline.
- ``write_store(tasks, next_id=None)``: write a valid ``tasks.json`` (schema in
  contracts/tasks-file.md) to set up a Given-state directly. Each task may be a partial dict;
  missing fields get the defaults of a freshly added task.
- ``read_store()``: parse ``tasks.json`` as JSON.
- ``list_lines(*extra)``: run ``todo list [extra...]`` and return its stdout lines.

``todo`` modules are imported as modules and their attributes are looked up at call time, so
before the implementation exists each test fails individually instead of breaking collection.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from todo import cli

STORE_NAME = "tasks.json"
SRC_DIR = Path(__file__).resolve().parent.parent / "src"


class Result(NamedTuple):
    code: int
    out: str
    err: str


def make_task(task_id: int, title: str, **fields: Any) -> dict[str, Any]:
    """Return a full task record for ``tasks.json`` with fresh-task defaults."""
    record: dict[str, Any] = {
        "id": task_id,
        "title": title,
        "status": "todo",
        "priority": "medium",
        "tags": [],
        "due": None,
    }
    record.update(fields)
    return record


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test inside an empty temporary working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def store_path(cli_env: Path) -> Path:
    """Path of ``tasks.json`` in the test's working directory."""
    return cli_env / STORE_NAME


@pytest.fixture
def run(cli_env: Path, capsys: pytest.CaptureFixture[str]) -> Callable[..., Result]:
    """Invoke the CLI in-process, like ``todo <args>`` in a new process."""

    def _run(*args: str) -> Result:
        capsys.readouterr()  # discard anything printed before this invocation
        try:
            code = cli.main(list(args))
        except SystemExit as exc:  # argparse --help / usage errors
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return _run


@pytest.fixture
def write_store(store_path: Path) -> Callable[..., Path]:
    """Write a valid ``tasks.json`` holding ``tasks``; return its path."""

    def _write(tasks: list[dict[str, Any]], next_id: int | None = None) -> Path:
        records = []
        for task in tasks:
            fields = dict(task)
            records.append(make_task(fields.pop("id"), fields.pop("title"), **fields))
        if next_id is None:
            next_id = max((r["id"] for r in records), default=0) + 1
        data = {"version": 1, "next_id": next_id, "tasks": records}
        store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return store_path

    return _write


@pytest.fixture
def read_store(store_path: Path) -> Callable[[], Any]:
    """Return a function that parses the current ``tasks.json``."""

    def _read() -> Any:
        return json.loads(store_path.read_text(encoding="utf-8"))

    return _read


@pytest.fixture
def list_lines(run: Callable[..., Result]) -> Callable[..., list[str]]:
    """Return a function running ``todo list [extra...]`` and giving its stdout lines."""

    def _list(*extra: str) -> list[str]:
        result = run("list", *extra)
        assert result.code == 0, result
        return result.out.splitlines()

    return _list
