"""Acceptance tests for ``todo list`` (FR-006 – FR-009, AC-017 – AC-024, AC-051)."""

from __future__ import annotations

STATUS_ERR = "Error: status must be one of: todo, in_progress, done.\n"


def _ids(lines: list[str]) -> list[int]:
    return [int(line.split(" | ", 1)[0]) for line in lines]


# --- Part 1: plain list and sorting (US1; FR-006, FR-007) --------------------------------


def test_ac017_empty_list(run, store_path):
    """AC-017: Given no tasks, When `todo list` runs, Then stdout is `No tasks found.` and exit
    code is 0."""
    assert run("list") == (0, "No tasks found.\n", "")
    assert not store_path.exists()


def test_ac018_sort_by_priority_then_creation(run, list_lines):
    """AC-018: Given tasks added in order 1 `A` (low), 2 `B` (high), 3 `C` (medium), 4 `D`
    (high), When `todo list` runs, Then stdout lines show ids in the order 2, 4, 3, 1 and exit
    code is 0."""
    for title, priority in [("A", "low"), ("B", "high"), ("C", "medium"), ("D", "high")]:
        assert run("add", title, "--priority", priority).code == 0
    lines = list_lines()
    assert _ids(lines) == [2, 4, 3, 1]
    assert lines == [
        "2 | todo | high | B | tags: - | due: -",
        "4 | todo | high | D | tags: - | due: -",
        "3 | todo | medium | C | tags: - | due: -",
        "1 | todo | low | A | tags: - | due: -",
    ]


# --- Part 2: filters (US3; FR-008, FR-009) -------------------------------------------------

AC019_TASKS = [
    {"id": 1, "title": "Write code", "tags": ["work"]},
    {"id": 2, "title": "Mow lawn", "tags": ["home"]},
    {"id": 3, "title": "Plan move", "tags": ["work", "home"]},
]
AC019_EXPECTED = (
    "1 | todo | medium | Write code | tags: work | due: -\n"
    "3 | todo | medium | Plan move | tags: work,home | due: -\n"
)


def test_ac019_filter_by_tag(run, write_store):
    """AC-019: Given task 1 tagged `work`, task 2 tagged `home`, task 3 tagged `work,home`,
    When `todo list --tag work` runs, Then stdout shows only tasks 1 and 3 (in sorted order)
    and exit code is 0."""
    write_store(AC019_TASKS)
    assert run("list", "--tag", "work") == (0, AC019_EXPECTED, "")


def test_ac019_filter_by_tag_via_cli_added_tasks(run):
    """AC-019 (tasks created through `todo add`): only tasks having the tag are shown."""
    assert run("add", "Write code", "--tags", "work").code == 0
    assert run("add", "Mow lawn", "--tags", "home").code == 0
    assert run("add", "Plan move", "--tags", "work,home").code == 0
    assert run("list", "--tag", "work") == (0, AC019_EXPECTED, "")


def test_ac020_filter_by_tag_case_insensitive(run, write_store):
    """AC-020: Given the tasks of AC-019, When `todo list --tag WORK` runs, Then output is
    identical to AC-019."""
    write_store(AC019_TASKS)
    assert run("list", "--tag", "WORK") == (0, AC019_EXPECTED, "")


def test_ac021_filter_by_unknown_tag(run, write_store):
    """AC-021: Given the tasks of AC-019, When `todo list --tag garden` runs, Then stdout is
    `No tasks found.` and exit code is 0."""
    write_store(AC019_TASKS)
    assert run("list", "--tag", "garden") == (0, "No tasks found.\n", "")


def test_ac022_filter_by_status(run, write_store):
    """AC-022: Given task 1 `Write report` in `todo` and task 2 `File taxes` in `done` (both
    medium, no tags, no due date), When `todo list --status done` runs, Then stdout is exactly
    `2 | done | medium | File taxes | tags: - | due: -` and exit code is 0."""
    write_store(
        [
            {"id": 1, "title": "Write report", "status": "todo"},
            {"id": 2, "title": "File taxes", "status": "done"},
        ]
    )
    assert run("list", "--status", "done") == (
        0,
        "2 | done | medium | File taxes | tags: - | due: -\n",
        "",
    )


def test_ac023_reject_invalid_status_filter(run, write_store):
    """AC-023: Given any tasks, When `todo list --status bogus` runs, Then stderr is
    `Error: status must be one of: todo, in_progress, done.` and exit code is 1."""
    write_store([{"id": 1, "title": "Write report"}])
    assert run("list", "--status", "bogus") == (1, "", STATUS_ERR)


def test_ac023_reject_invalid_status_filter_without_file(run):
    """AC-023 (no tasks.json at all): the invalid status value is still rejected."""
    assert run("list", "--status", "bogus") == (1, "", STATUS_ERR)


def test_ac024_filter_tag_and_status(run, write_store):
    """AC-024: Given task 1 tagged `work` status `done`, task 2 tagged `work` status `todo`,
    task 3 tagged `home` status `done`, When `todo list --tag work --status done` runs, Then
    stdout shows only task 1 and exit code is 0."""
    write_store(
        [
            {"id": 1, "title": "Ship release", "tags": ["work"], "status": "done"},
            {"id": 2, "title": "Review PR", "tags": ["work"], "status": "todo"},
            {"id": 3, "title": "Fix sink", "tags": ["home"], "status": "done"},
        ]
    )
    assert run("list", "--tag", "work", "--status", "done") == (
        0,
        "1 | done | medium | Ship release | tags: work | due: -\n",
        "",
    )


# --- Part 3: plain list shows every status (US2; FR-006) ----------------------------------


def test_ac051_plain_list_shows_all_statuses(run, write_store):
    """AC-051: Given task 1 `Write report` in `todo`, task 2 `Draft plan` in `in_progress` and
    task 3 `File taxes` in `done` (all medium, no tags, no due date), When `todo list` runs,
    Then stdout is exactly these three lines and exit code is 0:
    `1 | todo | medium | Write report | tags: - | due: -`,
    `2 | in_progress | medium | Draft plan | tags: - | due: -`,
    `3 | done | medium | File taxes | tags: - | due: -`."""
    write_store(
        [
            {"id": 1, "title": "Write report", "status": "todo"},
            {"id": 2, "title": "Draft plan", "status": "in_progress"},
            {"id": 3, "title": "File taxes", "status": "done"},
        ]
    )
    assert run("list") == (
        0,
        "1 | todo | medium | Write report | tags: - | due: -\n"
        "2 | in_progress | medium | Draft plan | tags: - | due: -\n"
        "3 | done | medium | File taxes | tags: - | due: -\n",
        "",
    )
