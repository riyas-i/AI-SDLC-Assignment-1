"""Acceptance tests for ``todo status`` and done-task rules (FR-013 – FR-015,
AC-033 – AC-039, AC-049, AC-050)."""

from __future__ import annotations

import pytest

STATUS_ERR = "Error: status must be one of: todo, in_progress, done.\n"


def _status_of(list_lines, task_id: int) -> str:
    for line in list_lines():
        fields = line.split(" | ")
        if int(fields[0]) == task_id:
            return fields[1]
    raise AssertionError(f"task {task_id} not in list")


# --- FR-013: allowed transitions -----------------------------------------------------------


def test_ac033_todo_to_in_progress(run, write_store, list_lines):
    """AC-033: Given task 1 in `todo`, When `todo status 1 in_progress` runs, Then stdout is
    `Task 1 status: todo -> in_progress` and exit code is 0."""
    write_store([{"id": 1, "title": "Write report", "status": "todo"}])
    assert run("status", "1", "in_progress") == (0, "Task 1 status: todo -> in_progress\n", "")
    assert _status_of(list_lines, 1) == "in_progress"


def test_ac034_in_progress_to_done(run, write_store, list_lines):
    """AC-034: Given task 1 in `in_progress`, When `todo status 1 done` runs, Then stdout is
    `Task 1 status: in_progress -> done` and exit code is 0."""
    write_store([{"id": 1, "title": "Write report", "status": "in_progress"}])
    assert run("status", "1", "done") == (0, "Task 1 status: in_progress -> done\n", "")
    assert _status_of(list_lines, 1) == "done"


def test_ac035_todo_to_done(run, write_store, list_lines):
    """AC-035: Given task 1 in `todo`, When `todo status 1 done` runs, Then stdout is
    `Task 1 status: todo -> done` and exit code is 0."""
    write_store([{"id": 1, "title": "Write report", "status": "todo"}])
    assert run("status", "1", "done") == (0, "Task 1 status: todo -> done\n", "")
    assert _status_of(list_lines, 1) == "done"


def test_ac033_ac034_full_workflow_via_cli(run, list_lines):
    """AC-033, AC-034 (User Story 2, scenario 1): a task added with `todo add` moves to
    `in_progress` and then to `done`."""
    assert run("add", "Write report").code == 0
    assert run("status", "1", "in_progress").code == 0
    assert run("status", "1", "done") == (0, "Task 1 status: in_progress -> done\n", "")
    assert list_lines() == ["1 | done | medium | Write report | tags: - | due: -"]


# --- FR-014: rejected transitions from todo / in_progress ----------------------------------


def test_ac036_in_progress_back_to_todo_rejected(run, write_store, list_lines):
    """AC-036: Given task 1 in `in_progress`, When `todo status 1 todo` runs, Then stderr is
    `Error: cannot change status from in_progress to todo.`, exit code is 1, and task 1 is
    still `in_progress`."""
    write_store([{"id": 1, "title": "Write report", "status": "in_progress"}])
    assert run("status", "1", "todo") == (
        1,
        "",
        "Error: cannot change status from in_progress to todo.\n",
    )
    assert _status_of(list_lines, 1) == "in_progress"


def test_ac037_todo_to_todo_rejected(run, write_store, list_lines):
    """AC-037: Given task 1 in `todo`, When `todo status 1 todo` runs, Then stderr is
    `Error: cannot change status from todo to todo.` and exit code is 1."""
    write_store([{"id": 1, "title": "Write report", "status": "todo"}])
    assert run("status", "1", "todo") == (1, "", "Error: cannot change status from todo to todo.\n")
    assert _status_of(list_lines, 1) == "todo"


def test_fr014_in_progress_to_in_progress_rejected(run, write_store, list_lines):
    """FR-014: any other change from `in_progress`, including to the same status, is rejected
    and leaves the task unchanged."""
    write_store([{"id": 1, "title": "Write report", "status": "in_progress"}])
    assert run("status", "1", "in_progress") == (
        1,
        "",
        "Error: cannot change status from in_progress to in_progress.\n",
    )
    assert _status_of(list_lines, 1) == "in_progress"


# --- FR-015: done is final -----------------------------------------------------------------


@pytest.mark.parametrize("target", ["todo", "in_progress", "done"])
def test_ac038_done_is_final(run, write_store, list_lines, target):
    """AC-038: Given task 1 in `done`, When `todo status 1 todo`, `todo status 1 in_progress`,
    or `todo status 1 done` runs, Then each prints to stderr
    `Error: task 1 is done; its status cannot be changed.`, exits with code 1, and task 1
    remains `done`."""
    write_store([{"id": 1, "title": "Write report", "status": "done"}])
    assert run("status", "1", target) == (
        1,
        "",
        "Error: task 1 is done; its status cannot be changed.\n",
    )
    assert _status_of(list_lines, 1) == "done"


def test_ac039_invalid_status_value(run, write_store, list_lines):
    """AC-039: Given task 1 in `todo`, When `todo status 1 finished` runs, Then stderr is
    `Error: status must be one of: todo, in_progress, done.` and exit code is 1."""
    write_store([{"id": 1, "title": "Write report", "status": "todo"}])
    assert run("status", "1", "finished") == (1, "", STATUS_ERR)
    assert _status_of(list_lines, 1) == "todo"


def test_ac049_edit_done_task(run, write_store, list_lines):
    """AC-049: Given task 1 `Buy milk` in `done`, When `todo update 1 --title "Buy oat milk"`
    runs, Then stdout is `Updated task 1.`, exit code is 0, and the task list is
    `1 | done | medium | Buy oat milk | tags: - | due: -`."""
    write_store([{"id": 1, "title": "Buy milk", "status": "done"}])
    assert run("update", "1", "--title", "Buy oat milk") == (0, "Updated task 1.\n", "")
    assert list_lines() == ["1 | done | medium | Buy oat milk | tags: - | due: -"]


def test_ac050_delete_done_task(run, write_store, list_lines):
    """AC-050: Given task 1 in `done`, When `todo delete 1` runs, Then stdout is
    `Deleted task 1.` and exit code is 0."""
    write_store([{"id": 1, "title": "Buy milk", "status": "done"}])
    assert run("delete", "1") == (0, "Deleted task 1.\n", "")
    assert list_lines() == ["No tasks found."]
