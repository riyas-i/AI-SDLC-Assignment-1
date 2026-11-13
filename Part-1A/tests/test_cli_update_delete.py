"""Acceptance tests for ``todo update`` / ``todo delete`` and id validation (FR-010 – FR-012,
AC-025 – AC-032, AC-052 – AC-054)."""

from __future__ import annotations

import pytest

TITLE_ERR = "Error: title must be 1-100 characters.\n"
DUE_ERR = "Error: due date must be a valid date in YYYY-MM-DD format.\n"
ID_ERR = "Error: task id must be a positive integer.\n"
NOTHING_ERR = "Error: nothing to update; provide --title, --priority, --tags or --due.\n"


# --- FR-010: update ------------------------------------------------------------------------


def test_ac025_update_title_only(run, write_store, list_lines):
    """AC-025: Given task 1 `Buy milk` (medium, tags `home`), When
    `todo update 1 --title "Buy oat milk"` runs, Then stdout is `Updated task 1.`, exit code is
    0, and the task list is `1 | todo | medium | Buy oat milk | tags: home | due: -`."""
    write_store([{"id": 1, "title": "Buy milk", "tags": ["home"]}])
    assert run("update", "1", "--title", "Buy oat milk") == (0, "Updated task 1.\n", "")
    assert list_lines() == ["1 | todo | medium | Buy oat milk | tags: home | due: -"]


def test_ac026_update_priority_and_tags(run, write_store, list_lines):
    """AC-026: Given task 1 `Buy milk`, When `todo update 1 --priority low --tags "shop,food"`
    runs, Then exit code is 0 and the task list is
    `1 | todo | low | Buy milk | tags: shop,food | due: -`."""
    write_store([{"id": 1, "title": "Buy milk"}])
    assert run("update", "1", "--priority", "low", "--tags", "shop,food") == (
        0,
        "Updated task 1.\n",
        "",
    )
    assert list_lines() == ["1 | todo | low | Buy milk | tags: shop,food | due: -"]


def test_ac027_clear_tags(run, write_store, list_lines):
    """AC-027: Given task 1 tagged `home`, When `todo update 1 --tags ""` runs, Then exit code
    is 0 and the task's line shows `tags: -`."""
    write_store([{"id": 1, "title": "Buy milk", "tags": ["home"]}])
    assert run("update", "1", "--tags", "").code == 0
    assert list_lines() == ["1 | todo | medium | Buy milk | tags: - | due: -"]


def test_ac028_reject_empty_title_on_update(run, write_store, list_lines):
    """AC-028: Given task 1 `Buy milk`, When `todo update 1 --title ""` runs, Then stderr is
    `Error: title must be 1-100 characters.`, exit code is 1, and task 1 is unchanged."""
    path = write_store([{"id": 1, "title": "Buy milk"}])
    before = path.read_bytes()
    assert run("update", "1", "--title", "") == (1, "", TITLE_ERR)
    assert path.read_bytes() == before
    assert list_lines() == ["1 | todo | medium | Buy milk | tags: - | due: -"]


def test_ac029_update_without_fields(run, write_store):
    """AC-029: Given task 1, When `todo update 1` runs with no fields, Then stderr is
    `Error: nothing to update; provide --title, --priority, --tags or --due.` and exit code
    is 1."""
    path = write_store([{"id": 1, "title": "Buy milk"}])
    before = path.read_bytes()
    assert run("update", "1") == (1, "", NOTHING_ERR)
    assert path.read_bytes() == before


def test_ac052_update_due_date(run, write_store, list_lines):
    """AC-052: Given task 1 `Pay rent` with no due date, When `todo update 1 --due 2026-12-15`
    runs, Then stdout is `Updated task 1.`, exit code is 0, and the task list is
    `1 | todo | medium | Pay rent | tags: - | due: 2026-12-15`."""
    write_store([{"id": 1, "title": "Pay rent"}])
    assert run("update", "1", "--due", "2026-12-15") == (0, "Updated task 1.\n", "")
    assert list_lines() == ["1 | todo | medium | Pay rent | tags: - | due: 2026-12-15"]


def test_ac053_clear_due_date(run, write_store, list_lines):
    """AC-053: Given task 1 with due date `2026-12-01`, When `todo update 1 --due ""` runs,
    Then exit code is 0 and the task's line shows `due: -`."""
    write_store([{"id": 1, "title": "Pay rent", "due": "2026-12-01"}])
    assert run("update", "1", "--due", "").code == 0
    assert list_lines() == ["1 | todo | medium | Pay rent | tags: - | due: -"]


def test_ac054_reject_invalid_due_on_update(run, write_store, list_lines):
    """AC-054: Given task 1 with due date `2026-12-01`, When `todo update 1 --due 2026-13-01`
    runs, Then stderr is `Error: due date must be a valid date in YYYY-MM-DD format.`, exit
    code is 1, and the due date is still `2026-12-01`."""
    write_store([{"id": 1, "title": "Pay rent", "due": "2026-12-01"}])
    assert run("update", "1", "--due", "2026-13-01") == (1, "", DUE_ERR)
    assert list_lines() == ["1 | todo | medium | Pay rent | tags: - | due: 2026-12-01"]


# --- FR-011: delete ------------------------------------------------------------------------


def test_ac030_delete_task(run, write_store, list_lines):
    """AC-030: Given tasks 1 and 2, When `todo delete 1` runs, Then stdout is
    `Deleted task 1.`, exit code is 0, and the task list shows only task 2."""
    write_store([{"id": 1, "title": "Buy milk"}, {"id": 2, "title": "Call bank"}])
    assert run("delete", "1") == (0, "Deleted task 1.\n", "")
    assert list_lines() == ["2 | todo | medium | Call bank | tags: - | due: -"]


# --- FR-012: id validation -----------------------------------------------------------------

ID_COMMANDS = [
    pytest.param(lambda i: ["delete", i], id="delete"),
    pytest.param(lambda i: ["update", i, "--title", "x"], id="update"),
    pytest.param(lambda i: ["status", i, "done"], id="status"),
]


@pytest.mark.parametrize("make_args", ID_COMMANDS)
def test_ac031_task_not_found(run, write_store, make_args):
    """AC-031: Given no task 99, When `todo delete 99` runs, Then stderr is
    `Error: task 99 not found.` and exit code is 1. The same message and exit code apply to
    `todo update 99 --title x` and `todo status 99 done`."""
    path = write_store([{"id": 1, "title": "Buy milk"}])
    before = path.read_bytes()
    assert run(*make_args("99")) == (1, "", "Error: task 99 not found.\n")
    assert path.read_bytes() == before


@pytest.mark.parametrize("make_args", ID_COMMANDS)
@pytest.mark.parametrize("bad_id", ["abc", "0", "-1"])
def test_ac032_invalid_id_format(run, write_store, make_args, bad_id):
    """AC-032: Given any tasks, When `todo delete abc` (or `0`, or `-1`) runs, Then stderr is
    `Error: task id must be a positive integer.` and exit code is 1.

    Also checked for `update` and `status` (FR-012)."""
    path = write_store([{"id": 1, "title": "Buy milk"}])
    before = path.read_bytes()
    assert run(*make_args(bad_id)) == (1, "", ID_ERR)
    assert path.read_bytes() == before
