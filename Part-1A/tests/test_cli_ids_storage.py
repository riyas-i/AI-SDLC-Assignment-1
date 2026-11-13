"""Acceptance tests for id allocation and storage safety (FR-016 – FR-019,
AC-040 – AC-046, AC-055)."""

from __future__ import annotations

import json
import os
import pathlib

import pytest
from conftest import make_task

CORRUPT_ERR = (
    "Error: tasks.json is corrupt and was not modified. Fix or remove it and try again.\n"
)
READ_ERR = "Error: could not read tasks.json.\n"
SAVE_ERR = "Error: could not save tasks.json; no changes were made.\n"


def _raw_bytes(path: pathlib.Path) -> bytes:
    """Read a file without going through ``Path.read_bytes`` (which AC-055 patches)."""
    with open(path, "rb") as handle:
        return handle.read()


# --- Part 1: ids are never reused (US4; FR-016) --------------------------------------------


def test_ac040_id_not_reused_after_delete_last(run):
    """AC-040: Given tasks 1, 2, 3, When `todo delete 3` then `todo add "Next"` run, Then the
    add prints `Added task 4: Next`."""
    for title in ("One", "Two", "Three"):
        assert run("add", title).code == 0
    assert run("delete", "3") == (0, "Deleted task 3.\n", "")
    assert run("add", "Next") == (0, "Added task 4: Next\n", "")


def test_ac041_id_not_reused_after_delete_all(run, list_lines):
    """AC-041: Given tasks 1 and 2, When both are deleted and `todo add "Fresh"` runs, Then it
    prints `Added task 3: Fresh` and the task list is
    `3 | todo | medium | Fresh | tags: - | due: -`."""
    assert run("add", "One").code == 0
    assert run("add", "Two").code == 0
    assert run("delete", "1").code == 0
    assert run("delete", "2").code == 0
    assert run("add", "Fresh") == (0, "Added task 3: Fresh\n", "")
    assert list_lines() == ["3 | todo | medium | Fresh | tags: - | due: -"]


# --- Part 2: persistence and corruption (US5; FR-017 – FR-019) ------------------------------


def test_ac042_persists_between_runs(run, store_path):
    """AC-042: Given `todo add "Buy milk"` has completed, When `todo list` runs as a new
    invocation, Then stdout is `1 | todo | medium | Buy milk | tags: - | due: -`."""
    assert run("add", "Buy milk").code == 0
    assert store_path.exists()
    assert run("list") == (0, "1 | todo | medium | Buy milk | tags: - | due: -\n", "")


def test_ac043_list_does_not_create_file(run, store_path):
    """AC-043: Given no `tasks.json`, When `todo list` runs, Then stdout is `No tasks found.`,
    exit code is 0, and `tasks.json` still does not exist."""
    assert run("list") == (0, "No tasks found.\n", "")
    assert not store_path.exists()


@pytest.mark.parametrize(
    "args",
    [pytest.param(["list"], id="list"), pytest.param(["add", "X"], id="add")],
)
def test_ac044_corrupt_json_untouched(run, store_path, args):
    """AC-044: Given `tasks.json` contains `{not json`, When `todo list` or `todo add "X"`
    runs, Then stderr is the corrupt-file message, exit code is 2, and the file content is
    still exactly `{not json`."""
    store_path.write_bytes(b"{not json")
    assert run(*args) == (2, "", CORRUPT_ERR)
    assert store_path.read_bytes() == b"{not json"


def _doc(**overrides):
    data = {"version": 1, "next_id": 2, "tasks": [make_task(1, "Buy milk")]}
    data.update(overrides)
    return json.dumps(data).encode("utf-8")


def _task_without_title():
    task = make_task(1, "Buy milk")
    del task["title"]
    return task


WRONG_STRUCTURES = [
    pytest.param(b"[]", id="top-level-list"),
    pytest.param(_doc(tasks=[_task_without_title()]), id="task-missing-title"),
    pytest.param(b"", id="empty-file"),
    pytest.param(
        _doc(next_id=3, tasks=[make_task(1, "A"), make_task(1, "B")]), id="duplicate-ids"
    ),
    pytest.param(_doc(tasks=[make_task(1, "A", status="finished")]), id="bad-status"),
    pytest.param(_doc(next_id=1), id="next-id-not-above-max-id"),
    pytest.param(_doc(notes="x"), id="unknown-top-level-key"),
    pytest.param(_doc(tasks=[make_task(1, "A", notes="x")]), id="unknown-task-key"),
]


@pytest.mark.parametrize("content", WRONG_STRUCTURES)
def test_ac045_wrong_structure_untouched(run, store_path, content):
    """AC-045: Given `tasks.json` contains valid JSON with the wrong structure (e.g. `[]`, a
    task record missing its title, or an otherwise valid file with an extra unknown field such
    as `"notes": "x"` at the top level or in a task), When `todo list` runs, Then stderr is the
    corrupt-file message, exit code is 2, and the file is unchanged.

    FR-018 also lists an empty file as corrupt."""
    store_path.write_bytes(content)
    assert run("list") == (2, "", CORRUPT_ERR)
    assert store_path.read_bytes() == content


def test_ac045_corrupt_file_wins_over_invalid_arguments(run, store_path):
    """AC-045 / contracts/cli.md check order: the file is loaded before arguments are
    validated, so a corrupt file gives exit 2 even when the arguments are also invalid."""
    store_path.write_bytes(b"[]")
    assert run("add", "") == (2, "", CORRUPT_ERR)
    assert store_path.read_bytes() == b"[]"


def test_ac055_unreadable_file_exit2(run, write_store, monkeypatch):
    """AC-055: Given `tasks.json` exists but cannot be read (opening it fails with an access
    error), When `todo list` runs, Then stderr is `Error: could not read tasks.json.`, stdout
    is empty, and exit code is 2."""
    path = write_store([{"id": 1, "title": "Buy milk"}])
    before = _raw_bytes(path)
    original_read_bytes = pathlib.Path.read_bytes

    def raiser(self, *args, **kwargs):
        if self.name == "tasks.json":
            raise PermissionError(13, "Permission denied", str(self))
        return original_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_bytes", raiser)
    assert run("list") == (2, "", READ_ERR)
    assert _raw_bytes(path) == before


def test_ac046_save_failure_keeps_file(run, write_store, cli_env, monkeypatch):
    """AC-046: Given `tasks.json` holds task 1 and the file cannot be written (e.g. the location
    is read-only or the write is interrupted), When `todo add "X"` runs, Then stderr is the
    save-failure message, exit code is 2, and `tasks.json` is byte-for-byte unchanged."""
    path = write_store([{"id": 1, "title": "Buy milk"}])
    before = path.read_bytes()

    def raiser(*args, **kwargs):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(os, "replace", raiser)
    assert run("add", "X") == (2, "", SAVE_ERR)
    assert path.read_bytes() == before
    assert list(cli_env.glob(".tasks-*.tmp")) == []
