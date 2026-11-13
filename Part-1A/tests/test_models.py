"""Unit tests for the validators and domain types in ``todo.models`` (data-model.md;
FR-002 – FR-005, FR-012 – FR-015).

Attributes are looked up on the module at call time so each test fails on its own until the
implementation exists.
"""

from __future__ import annotations

import pytest

from todo import models

TITLE_MSG = "title must be 1-100 characters."
PRIORITY_MSG = "priority must be one of: low, medium, high."
TAG_MSG = "each tag must be 1-30 characters using only letters, digits, '-' or '_'."
DUE_MSG = "due date must be a valid date in YYYY-MM-DD format."
STATUS_MSG = "status must be one of: todo, in_progress, done."
ID_MSG = "task id must be a positive integer."


def _rejects(func, value, message):
    with pytest.raises(models.ValidationError) as excinfo:
        func(value)
    assert str(excinfo.value) == message


# --- Types and error hierarchy -------------------------------------------------------------


def test_unit_error_hierarchy():
    assert issubclass(models.ValidationError, models.TodoError)
    assert issubclass(models.NotFoundError, models.ValidationError)


def test_unit_enum_values():
    assert [s.value for s in models.Status] == ["todo", "in_progress", "done"]
    assert [p.value for p in models.Priority] == ["low", "medium", "high"]


def test_ac018_priority_rank_orders_high_medium_low():
    rank = models.PRIORITY_RANK
    assert rank[models.Priority.HIGH] < rank[models.Priority.MEDIUM] < rank[models.Priority.LOW]


def test_unit_task_dict_round_trip():
    record = {
        "id": 3,
        "title": "Café ☕",
        "status": "in_progress",
        "priority": "high",
        "tags": ["home", "bills"],
        "due": "2026-12-01",
    }
    task = models.Task.from_dict(record)
    assert task.id == 3
    assert task.status == models.Status.IN_PROGRESS
    assert task.priority == models.Priority.HIGH
    assert task.to_dict() == record


# --- validate_title (FR-002) ---------------------------------------------------------------


def test_ac003_validate_title_accepts_100_chars():
    assert models.validate_title("a" * 100) == "a" * 100


def test_ac003_validate_title_counts_characters():
    title = "é" * 99 + "☕"
    assert models.validate_title(title) == title


def test_ac004_validate_title_rejects_101_chars():
    _rejects(models.validate_title, "a" * 101, TITLE_MSG)


def test_ac005_validate_title_rejects_empty():
    _rejects(models.validate_title, "", TITLE_MSG)


def test_ac006_validate_title_rejects_blank():
    _rejects(models.validate_title, "   ", TITLE_MSG)


def test_ac007_validate_title_strips():
    assert models.validate_title("  Buy milk  ") == "Buy milk"


def test_unit_validate_title_length_measured_after_strip():
    assert models.validate_title("  " + "a" * 100 + "  ") == "a" * 100


# --- parse_priority (FR-003) ---------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [("low", "low"), ("medium", "medium"), ("high", "high")])
def test_unit_parse_priority_valid(raw, expected):
    assert models.parse_priority(raw) == models.Priority(expected)


@pytest.mark.parametrize("raw", ["HIGH", "High", "hIgH"])
def test_ac010_parse_priority_case_insensitive(raw):
    assert models.parse_priority(raw) == models.Priority.HIGH


@pytest.mark.parametrize("raw", ["urgent", "", "highest", "1"])
def test_ac009_parse_priority_rejects_unknown(raw):
    _rejects(models.parse_priority, raw, PRIORITY_MSG)


# --- parse_tags (FR-004) -------------------------------------------------------------------


def test_ac011_parse_tags_splits_and_trims():
    assert models.parse_tags("work, urgent") == ["work", "urgent"]


def test_ac012_tags_dedup_lowercase():
    assert models.parse_tags("Work,work,") == ["work"]


def test_unit_parse_tags_keeps_first_occurrence_order():
    assert models.parse_tags("b,A,c,a,B") == ["b", "a", "c"]


def test_ac027_parse_tags_empty_string_is_no_tags():
    assert models.parse_tags("") == []


def test_unit_parse_tags_drops_empty_entries():
    assert models.parse_tags(" , ,ok,") == ["ok"]


@pytest.mark.parametrize("raw", ["a" * 30, "a_b-1", "X9"])
def test_unit_parse_tags_accepts_valid_tags(raw):
    assert models.parse_tags(raw) == [raw.lower()]


@pytest.mark.parametrize("raw", ["bad tag", "a" * 31, "x!", "work,ok?", "café"])
def test_ac013_parse_tags_rejects_invalid(raw):
    _rejects(models.parse_tags, raw, TAG_MSG)


# --- parse_due (FR-005, FR-010) ------------------------------------------------------------


def test_ac014_parse_due_valid():
    assert models.parse_due("2026-12-01") == "2026-12-01"


def test_unit_parse_due_past_date_allowed():
    assert models.parse_due("1999-01-31") == "1999-01-31"


def test_unit_parse_due_leap_day():
    assert models.parse_due("2028-02-29") == "2028-02-29"


def test_ac053_parse_due_empty_is_none():
    assert models.parse_due("") is None


def test_ac015_parse_due_rejects_impossible_date():
    _rejects(models.parse_due, "2026-02-30", DUE_MSG)


def test_ac016_parse_due_rejects_wrong_format():
    _rejects(models.parse_due, "01-12-2026", DUE_MSG)


def test_ac054_parse_due_rejects_month_13():
    _rejects(models.parse_due, "2026-13-01", DUE_MSG)


@pytest.mark.parametrize("raw", ["2026-1-01", "2026-12-1", "20261201", "2026-12-01x", "tomorrow"])
def test_unit_parse_due_rejects_malformed(raw):
    _rejects(models.parse_due, raw, DUE_MSG)


# --- parse_status (FR-009, FR-015) ---------------------------------------------------------


@pytest.mark.parametrize("raw", ["todo", "in_progress", "done"])
def test_unit_parse_status_valid(raw):
    assert models.parse_status(raw) == models.Status(raw)


def test_ac039_parse_status_rejects_finished():
    _rejects(models.parse_status, "finished", STATUS_MSG)


def test_ac023_parse_status_rejects_bogus():
    _rejects(models.parse_status, "bogus", STATUS_MSG)


@pytest.mark.parametrize("raw", ["DONE", "in-progress", ""])
def test_unit_parse_status_is_exact(raw):
    _rejects(models.parse_status, raw, STATUS_MSG)


# --- parse_task_id (FR-012) ----------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [("1", 1), ("42", 42), ("1000", 1000)])
def test_unit_parse_task_id_valid(raw, expected):
    assert models.parse_task_id(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "0", "-1"])
def test_ac032_parse_task_id_rejects(raw):
    _rejects(models.parse_task_id, raw, ID_MSG)


@pytest.mark.parametrize("raw", ["", "1.5", "+1", " 1", "00"])
def test_unit_parse_task_id_rejects_other_forms(raw):
    _rejects(models.parse_task_id, raw, ID_MSG)


# --- check_transition (FR-013 – FR-015; full table in data-model.md) -----------------------


@pytest.mark.parametrize(
    "old, new",
    [("todo", "in_progress"), ("in_progress", "done"), ("todo", "done")],
)
def test_ac033_ac034_ac035_allowed_transitions(old, new):
    models.check_transition(1, models.Status(old), models.Status(new))  # must not raise


@pytest.mark.parametrize(
    "old, new",
    [("todo", "todo"), ("in_progress", "todo"), ("in_progress", "in_progress")],
)
def test_ac036_ac037_rejected_transitions(old, new):
    with pytest.raises(models.ValidationError) as excinfo:
        models.check_transition(1, models.Status(old), models.Status(new))
    assert str(excinfo.value) == f"cannot change status from {old} to {new}."


@pytest.mark.parametrize("new", ["todo", "in_progress", "done"])
def test_ac038_transition_from_done_rejected(new):
    with pytest.raises(models.ValidationError) as excinfo:
        models.check_transition(7, models.Status.DONE, models.Status(new))
    assert str(excinfo.value) == "task 7 is done; its status cannot be changed."
