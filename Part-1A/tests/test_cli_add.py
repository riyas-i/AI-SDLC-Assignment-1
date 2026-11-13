"""Acceptance tests for ``todo add`` (FR-001 – FR-005, AC-001 – AC-016)."""

from __future__ import annotations

TITLE_ERR = "Error: title must be 1-100 characters.\n"
PRIORITY_ERR = "Error: priority must be one of: low, medium, high.\n"
TAG_ERR = "Error: each tag must be 1-30 characters using only letters, digits, '-' or '_'.\n"
DUE_ERR = "Error: due date must be a valid date in YYYY-MM-DD format.\n"


# --- FR-001 -------------------------------------------------------------------------------


def test_ac001_add_first_task(run, list_lines):
    """AC-001: Given no tasks, When `todo add "Buy milk"` runs, Then stdout is
    `Added task 1: Buy milk`, exit code is 0, and the task list is exactly
    `1 | todo | medium | Buy milk | tags: - | due: -`."""
    assert run("add", "Buy milk") == (0, "Added task 1: Buy milk\n", "")
    assert list_lines() == ["1 | todo | medium | Buy milk | tags: - | due: -"]


def test_ac002_add_second_task_gets_next_id(run):
    """AC-002: Given task 1 exists, When `todo add "Call bank"` runs, Then stdout is
    `Added task 2: Call bank` and exit code is 0."""
    assert run("add", "Buy milk").code == 0
    assert run("add", "Call bank") == (0, "Added task 2: Call bank\n", "")


# --- FR-002 -------------------------------------------------------------------------------


def test_ac003_title_of_100_chars_accepted(run, list_lines):
    """AC-003: Given no tasks, When `todo add` runs with a title of exactly 100 `a` characters,
    Then exit code is 0 and the task is stored with that title."""
    title = "a" * 100
    assert run("add", title) == (0, f"Added task 1: {title}\n", "")
    assert list_lines() == [f"1 | todo | medium | {title} | tags: - | due: -"]


def test_ac003_title_length_counts_characters_not_bytes(run, read_store):
    """AC-003 / Edge case: length counts characters, so a 100-character non-ASCII title such as
    one ending in `Café ☕` is accepted and stored unchanged."""
    title = "x" * 94 + "Café ☕"
    assert len(title) == 100
    assert run("add", title).code == 0
    assert read_store()["tasks"][0]["title"] == title


def test_ac004_title_of_101_chars_rejected(run, store_path):
    """AC-004: Given no tasks, When `todo add` runs with a title of 101 `a` characters, Then
    stderr is `Error: title must be 1-100 characters.`, exit code is 1, and no task is
    created."""
    assert run("add", "a" * 101) == (1, "", TITLE_ERR)
    assert not store_path.exists()


def test_ac005_empty_title_rejected(run, store_path):
    """AC-005: Given no tasks, When `todo add ""` runs, Then stderr is
    `Error: title must be 1-100 characters.` and exit code is 1."""
    assert run("add", "") == (1, "", TITLE_ERR)
    assert not store_path.exists()


def test_ac006_blank_title_rejected(run, store_path):
    """AC-006: Given no tasks, When `todo add "   "` runs, Then stderr is
    `Error: title must be 1-100 characters.` and exit code is 1."""
    assert run("add", "   ") == (1, "", TITLE_ERR)
    assert not store_path.exists()


def test_ac007_title_is_trimmed(run, read_store):
    """AC-007: Given no tasks, When `todo add "  Buy milk  "` runs, Then stdout is
    `Added task 1: Buy milk` and the stored title is `Buy milk`."""
    assert run("add", "  Buy milk  ") == (0, "Added task 1: Buy milk\n", "")
    assert read_store()["tasks"][0]["title"] == "Buy milk"


# --- FR-003 -------------------------------------------------------------------------------


def test_ac008_add_with_priority_high(run, list_lines):
    """AC-008: Given no tasks, When `todo add "Pay rent" --priority high` runs, Then exit code
    is 0 and the task list is `1 | todo | high | Pay rent | tags: - | due: -`."""
    assert run("add", "Pay rent", "--priority", "high").code == 0
    assert list_lines() == ["1 | todo | high | Pay rent | tags: - | due: -"]


def test_ac009_reject_unknown_priority(run, store_path):
    """AC-009: Given no tasks, When `todo add "Pay rent" --priority urgent` runs, Then stderr is
    `Error: priority must be one of: low, medium, high.`, exit code is 1, and no task is
    created."""
    assert run("add", "Pay rent", "--priority", "urgent") == (1, "", PRIORITY_ERR)
    assert not store_path.exists()


def test_ac010_priority_case_insensitive_stored_lower(run, read_store, list_lines):
    """AC-010: Given no tasks, When `todo add "Pay rent" --priority HIGH` runs, Then exit code
    is 0 and the stored priority is `high`."""
    assert run("add", "Pay rent", "--priority", "HIGH").code == 0
    assert read_store()["tasks"][0]["priority"] == "high"
    assert list_lines() == ["1 | todo | high | Pay rent | tags: - | due: -"]


# --- FR-004 -------------------------------------------------------------------------------


def test_ac011_add_with_tags(run, list_lines):
    """AC-011: Given no tasks, When `todo add "Fix bug" --tags "work, urgent"` runs, Then the
    task list is `1 | todo | medium | Fix bug | tags: work,urgent | due: -`."""
    assert run("add", "Fix bug", "--tags", "work, urgent").code == 0
    assert list_lines() == ["1 | todo | medium | Fix bug | tags: work,urgent | due: -"]


def test_ac012_tags_deduplicated_and_lowercased(run, list_lines):
    """AC-012: Given no tasks, When `todo add "Fix bug" --tags "Work,work,"` runs, Then the
    task list is `1 | todo | medium | Fix bug | tags: work | due: -`."""
    assert run("add", "Fix bug", "--tags", "Work,work,").code == 0
    assert list_lines() == ["1 | todo | medium | Fix bug | tags: work | due: -"]


def test_ac013_reject_invalid_tag(run, store_path):
    """AC-013: Given no tasks, When `todo add "Fix bug" --tags "bad tag"` runs, Then stderr is
    `Error: each tag must be 1-30 characters using only letters, digits, '-' or '_'.`, exit
    code is 1, and no task is created."""
    assert run("add", "Fix bug", "--tags", "bad tag") == (1, "", TAG_ERR)
    assert not store_path.exists()


# --- FR-005 -------------------------------------------------------------------------------


def test_ac014_add_with_due_date(run, list_lines):
    """AC-014: Given no tasks, When `todo add "Pay rent" --due 2026-12-01` runs, Then the task
    list is `1 | todo | medium | Pay rent | tags: - | due: 2026-12-01`."""
    assert run("add", "Pay rent", "--due", "2026-12-01").code == 0
    assert list_lines() == ["1 | todo | medium | Pay rent | tags: - | due: 2026-12-01"]


def test_ac014_past_due_date_accepted(run, list_lines):
    """AC-014 / Edge case: a due date in the past is accepted (the tool does not judge
    deadlines)."""
    assert run("add", "Old thing", "--due", "2001-01-31").code == 0
    assert list_lines() == ["1 | todo | medium | Old thing | tags: - | due: 2001-01-31"]


def test_ac015_reject_impossible_date(run, store_path):
    """AC-015: Given no tasks, When `todo add "Pay rent" --due 2026-02-30` runs, Then stderr is
    `Error: due date must be a valid date in YYYY-MM-DD format.`, exit code is 1, and no task
    is created."""
    assert run("add", "Pay rent", "--due", "2026-02-30") == (1, "", DUE_ERR)
    assert not store_path.exists()


def test_ac016_reject_wrong_date_format(run, store_path):
    """AC-016: Given no tasks, When `todo add "Pay rent" --due 01-12-2026` runs, Then stderr is
    `Error: due date must be a valid date in YYYY-MM-DD format.` and exit code is 1."""
    assert run("add", "Pay rent", "--due", "01-12-2026") == (1, "", DUE_ERR)
    assert not store_path.exists()
