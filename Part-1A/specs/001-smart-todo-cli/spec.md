# Feature Specification: Smart Todo CLI

**Feature Branch**: `main` (no feature branch; solo assignment works on the current branch)

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Build a command-line Todo manager for a single developer managing
personal tasks from the terminal. Add task: title required (1-100 characters), priority
low/medium/high (default medium), optional tags, optional due date in YYYY-MM-DD format. List
tasks: filter by tag and by status; sort by priority (high > medium > low), ties broken by
creation order. Update a task's title, priority or tags; delete a task by id. Status transitions:
todo -> in_progress -> done, and todo -> done directly. done is final; any change out of done is
rejected with an error. IDs are sequential integers and are never reused after a delete. Data is
saved to tasks.json. If the file is corrupt, show a clear error and do not overwrite it."

## Command Interface (reference for all acceptance criteria)

The tool is invoked as `todo <command> [arguments]`. Acceptance criteria below use this syntax.

| Command | Form |
|---------|------|
| Add | `todo add "<title>" [--priority low\|medium\|high] [--tags <t1,t2,...>] [--due YYYY-MM-DD]` |
| List | `todo list [--tag <tag>] [--status todo\|in_progress\|done]` |
| Update | `todo update <id> [--title "<title>"] [--priority <p>] [--tags <t1,t2,...>]` |
| Delete | `todo delete <id>` |
| Change status | `todo status <id> <todo\|in_progress\|done>` |
| Help | `todo --help` |

**Output conventions**

- Success messages go to standard output (stdout); error messages go to standard error (stderr)
  and start with `Error: `. A failing command prints nothing to stdout.
- Exit codes: `0` success, `1` user/validation error, `2` storage error.
- `todo list` prints one line per task in this exact format:

  `<id> | <status> | <priority> | <title> | tags: <tags> | due: <due>`

  where `<tags>` is the task's tags joined by `,` in the order stored (or `-` if none) and
  `<due>` is the due date (or `-` if none). Example:

  `2 | todo | high | Pay rent | tags: home,bills | due: 2026-12-01`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture and see tasks (Priority: P1)

As a developer, I add tasks from the terminal and list them ordered by priority so I always know
what to work on next.

**Why this priority**: Adding and listing is the minimum useful product; everything else builds on
it.

**Independent Test**: In an empty directory, add several tasks with different priorities and
verify `todo list` shows them in priority order (AC-001 – AC-018).

**Acceptance Scenarios**:

1. **Given** no tasks, **When** the user runs `todo add "Buy milk"`, **Then** the task is saved
   with id 1, status `todo`, priority `medium` (AC-001).
2. **Given** tasks of mixed priority, **When** the user runs `todo list`, **Then** tasks appear
   high → medium → low, ties in creation order (AC-018).

---

### User Story 2 - Track progress through statuses (Priority: P2)

As a developer, I move tasks from `todo` to `in_progress` to `done`, and once a task is done it
stays done.

**Why this priority**: Status tracking turns a list into a workflow, but requires tasks to exist
first.

**Independent Test**: Add a task, advance it through each allowed status, and confirm every
disallowed transition is rejected (AC-033 – AC-039).

**Acceptance Scenarios**:

1. **Given** a `todo` task, **When** the user sets it to `in_progress` then `done`, **Then** both
   changes succeed (AC-033, AC-034).
2. **Given** a `done` task, **When** the user tries any status change, **Then** it is rejected
   with exit code 1 (AC-038).

---

### User Story 3 - Filter the list (Priority: P3)

As a developer, I filter my list by tag and/or status to focus on one area of work.

**Why this priority**: Valuable once the list grows; not needed for a first useful release.

**Independent Test**: Add tagged tasks with different statuses and verify each filter
combination (AC-019 – AC-024).

**Acceptance Scenarios**:

1. **Given** tasks tagged `work` and `home`, **When** the user runs `todo list --tag work`,
   **Then** only `work` tasks are shown (AC-019).

---

### User Story 4 - Edit and remove tasks (Priority: P3)

As a developer, I fix a task's title, priority or tags, or delete it entirely.

**Why this priority**: Corrections are routine but secondary to capture and tracking.

**Independent Test**: Add a task, update each field, delete it, and confirm ids are not reused
(AC-025 – AC-032, AC-040 – AC-041).

**Acceptance Scenarios**:

1. **Given** task 1, **When** the user runs `todo update 1 --title "New"`, **Then** only the title
   changes (AC-025).
2. **Given** tasks 1–3, **When** task 3 is deleted and a new task is added, **Then** the new task
   gets id 4 (AC-040).

---

### User Story 5 - Data is safe (Priority: P2)

As a developer, I trust that my tasks persist between runs and that a damaged data file is never
silently overwritten.

**Why this priority**: Losing task data destroys trust in the tool.

**Independent Test**: Corrupt `tasks.json`, run commands, and confirm the file is byte-for-byte
unchanged and exit code is 2 (AC-042 – AC-046).

**Acceptance Scenarios**:

1. **Given** a corrupt `tasks.json`, **When** the user runs any command, **Then** a clear error is
   shown, exit code is 2, and the file is untouched (AC-044).

---

### Edge Cases

- Title is exactly 100 characters (accepted) or 101 characters (rejected); length counts
  characters, not bytes, so non-ASCII titles such as `Café ☕` are measured by character count.
- Title consists only of spaces (rejected after trimming).
- Due date that looks right but is not a real date, e.g. `2026-02-30` (rejected).
- Due date in the past (accepted; the tool does not judge deadlines).
- Duplicate or differently-cased tags, e.g. `Work,work` (stored once, lower-case).
- Deleting the highest id, or every task, then adding a new task (id is never reused).
- `tasks.json` missing (treated as empty), empty (0 bytes), invalid JSON, or valid JSON with the
  wrong structure (all except "missing" are corrupt).
- Saving fails partway (previous file contents remain intact).
- Task id given as `abc`, `0`, or `-1` (rejected as not a positive integer).

## Requirements *(mandatory)*

### Functional Requirements

Acceptance criteria are numbered globally (AC-001 … AC-048). Unless stated otherwise, each
criterion starts from an empty working directory with no `tasks.json`, and "the task list" means
the output of `todo list`.

#### Adding tasks

- **FR-001**: Users MUST be able to add a task with a title. A new task gets the next id, status
  `todo`, priority `medium`, no tags and no due date unless given.
  - **AC-001**: **Given** no tasks, **When** `todo add "Buy milk"` runs, **Then** stdout is
    `Added task 1: Buy milk`, exit code is 0, and the task list is exactly
    `1 | todo | medium | Buy milk | tags: - | due: -`.
  - **AC-002**: **Given** task 1 exists, **When** `todo add "Call bank"` runs, **Then** stdout is
    `Added task 2: Call bank` and exit code is 0.

- **FR-002**: The title MUST be 1–100 characters after leading and trailing whitespace is removed;
  the trimmed title is what is stored.
  - **AC-003**: **Given** no tasks, **When** `todo add` runs with a title of exactly 100 `a`
    characters, **Then** exit code is 0 and the task is stored with that title.
  - **AC-004**: **Given** no tasks, **When** `todo add` runs with a title of 101 `a` characters,
    **Then** stderr is `Error: title must be 1-100 characters.`, exit code is 1, and no task is
    created.
  - **AC-005**: **Given** no tasks, **When** `todo add ""` runs, **Then** stderr is
    `Error: title must be 1-100 characters.` and exit code is 1.
  - **AC-006**: **Given** no tasks, **When** `todo add "   "` runs, **Then** stderr is
    `Error: title must be 1-100 characters.` and exit code is 1.
  - **AC-007**: **Given** no tasks, **When** `todo add "  Buy milk  "` runs, **Then** stdout is
    `Added task 1: Buy milk` and the stored title is `Buy milk`.

- **FR-003**: Priority MUST be one of `low`, `medium`, `high` (case-insensitive, stored
  lower-case); default `medium`.
  - **AC-008**: **Given** no tasks, **When** `todo add "Pay rent" --priority high` runs,
    **Then** exit code is 0 and the task list is `1 | todo | high | Pay rent | tags: - | due: -`.
  - **AC-009**: **Given** no tasks, **When** `todo add "Pay rent" --priority urgent` runs,
    **Then** stderr is `Error: priority must be one of: low, medium, high.`, exit code is 1, and
    no task is created.
  - **AC-010**: **Given** no tasks, **When** `todo add "Pay rent" --priority HIGH` runs, **Then**
    exit code is 0 and the stored priority is `high`.

- **FR-004**: Tags are optional, given as a comma-separated list. Each tag is trimmed and
  lower-cased; empty entries are ignored; duplicates are removed keeping first occurrence order.
  Each tag MUST be 1–30 characters of letters, digits, `-` or `_`.
  - **AC-011**: **Given** no tasks, **When** `todo add "Fix bug" --tags "work, urgent"` runs,
    **Then** the task list is `1 | todo | medium | Fix bug | tags: work,urgent | due: -`.
  - **AC-012**: **Given** no tasks, **When** `todo add "Fix bug" --tags "Work,work,"` runs,
    **Then** the task list is `1 | todo | medium | Fix bug | tags: work | due: -`.
  - **AC-013**: **Given** no tasks, **When** `todo add "Fix bug" --tags "bad tag"` runs, **Then**
    stderr is `Error: each tag must be 1-30 characters using only letters, digits, '-' or '_'.`,
    exit code is 1, and no task is created.

- **FR-005**: The due date is optional and MUST be a real calendar date in `YYYY-MM-DD` format.
  Past dates are allowed.
  - **AC-014**: **Given** no tasks, **When** `todo add "Pay rent" --due 2026-12-01` runs,
    **Then** the task list is `1 | todo | medium | Pay rent | tags: - | due: 2026-12-01`.
  - **AC-015**: **Given** no tasks, **When** `todo add "Pay rent" --due 2026-02-30` runs,
    **Then** stderr is `Error: due date must be a valid date in YYYY-MM-DD format.`, exit code
    is 1, and no task is created.
  - **AC-016**: **Given** no tasks, **When** `todo add "Pay rent" --due 01-12-2026` runs,
    **Then** stderr is `Error: due date must be a valid date in YYYY-MM-DD format.` and exit code
    is 1.

#### Listing tasks

- **FR-006**: `todo list` MUST print every task in the line format defined in Command Interface,
  or `No tasks found.` when there is nothing to show.
  - **AC-017**: **Given** no tasks, **When** `todo list` runs, **Then** stdout is
    `No tasks found.` and exit code is 0.

- **FR-007**: The list MUST be sorted by priority (high, then medium, then low); tasks with equal
  priority appear in creation order (ascending id).
  - **AC-018**: **Given** tasks added in order 1 `A` (low), 2 `B` (high), 3 `C` (medium),
    4 `D` (high), **When** `todo list` runs, **Then** stdout lines show ids in the order
    2, 4, 3, 1 and exit code is 0.

- **FR-008**: `todo list --tag <tag>` MUST show only tasks having that tag (case-insensitive).
  - **AC-019**: **Given** task 1 tagged `work`, task 2 tagged `home`, task 3 tagged `work,home`,
    **When** `todo list --tag work` runs, **Then** stdout shows only tasks 1 and 3 (in sorted
    order) and exit code is 0.
  - **AC-020**: **Given** the tasks of AC-019, **When** `todo list --tag WORK` runs, **Then**
    output is identical to AC-019.
  - **AC-021**: **Given** the tasks of AC-019, **When** `todo list --tag garden` runs, **Then**
    stdout is `No tasks found.` and exit code is 0.

- **FR-009**: `todo list --status <status>` MUST show only tasks in that status. Combined `--tag`
  and `--status` filters MUST both apply.
  - **AC-022**: **Given** task 1 `Write report` in `todo` and task 2 `File taxes` in `done` (both
    medium, no tags, no due date), **When** `todo list --status done` runs, **Then** stdout is
    exactly `2 | done | medium | File taxes | tags: - | due: -` and exit code is 0.
  - **AC-023**: **Given** any tasks, **When** `todo list --status bogus` runs, **Then** stderr is
    `Error: status must be one of: todo, in_progress, done.` and exit code is 1.
  - **AC-024**: **Given** task 1 tagged `work` status `done`, task 2 tagged `work` status `todo`,
    task 3 tagged `home` status `done`, **When** `todo list --tag work --status done` runs,
    **Then** stdout shows only task 1 and exit code is 0.

#### Updating and deleting tasks

- **FR-010**: Users MUST be able to update a task's title, priority and/or tags. Only the given
  fields change. New values follow the same rules as FR-002–FR-004. `--tags ""` removes all tags.
  At least one field MUST be given.
  - **AC-025**: **Given** task 1 `Buy milk` (medium, tags `home`), **When**
    `todo update 1 --title "Buy oat milk"` runs, **Then** stdout is `Updated task 1.`, exit code
    is 0, and the task list is `1 | todo | medium | Buy oat milk | tags: home | due: -`.
  - **AC-026**: **Given** task 1 `Buy milk`, **When**
    `todo update 1 --priority low --tags "shop,food"` runs, **Then** exit code is 0 and the task
    list is `1 | todo | low | Buy milk | tags: shop,food | due: -`.
  - **AC-027**: **Given** task 1 tagged `home`, **When** `todo update 1 --tags ""` runs, **Then**
    exit code is 0 and the task's line shows `tags: -`.
  - **AC-028**: **Given** task 1 `Buy milk`, **When** `todo update 1 --title ""` runs, **Then**
    stderr is `Error: title must be 1-100 characters.`, exit code is 1, and task 1 is unchanged.
  - **AC-029**: **Given** task 1, **When** `todo update 1` runs with no fields, **Then** stderr is
    `Error: nothing to update; provide --title, --priority or --tags.` and exit code is 1.

- **FR-011**: Users MUST be able to delete a task by id.
  - **AC-030**: **Given** tasks 1 and 2, **When** `todo delete 1` runs, **Then** stdout is
    `Deleted task 1.`, exit code is 0, and the task list shows only task 2.

- **FR-012**: Commands that take an id (`update`, `delete`, `status`) MUST reject ids that are not
  positive integers or do not exist.
  - **AC-031**: **Given** no task 99, **When** `todo delete 99` runs, **Then** stderr is
    `Error: task 99 not found.` and exit code is 1. The same message and exit code apply to
    `todo update 99 --title x` and `todo status 99 done`.
  - **AC-032**: **Given** any tasks, **When** `todo delete abc` (or `0`, or `-1`) runs, **Then**
    stderr is `Error: task id must be a positive integer.` and exit code is 1.

#### Status transitions

- **FR-013**: Allowed status changes are exactly: `todo → in_progress`, `in_progress → done`,
  `todo → done`. A successful change prints `Task <id> status: <old> -> <new>`.
  - **AC-033**: **Given** task 1 in `todo`, **When** `todo status 1 in_progress` runs, **Then**
    stdout is `Task 1 status: todo -> in_progress` and exit code is 0.
  - **AC-034**: **Given** task 1 in `in_progress`, **When** `todo status 1 done` runs, **Then**
    stdout is `Task 1 status: in_progress -> done` and exit code is 0.
  - **AC-035**: **Given** task 1 in `todo`, **When** `todo status 1 done` runs, **Then** stdout
    is `Task 1 status: todo -> done` and exit code is 0.

- **FR-014**: Any other change from `todo` or `in_progress` (including to the same status) MUST be
  rejected and leave the task unchanged.
  - **AC-036**: **Given** task 1 in `in_progress`, **When** `todo status 1 todo` runs, **Then**
    stderr is `Error: cannot change status from in_progress to todo.`, exit code is 1, and task 1
    is still `in_progress`.
  - **AC-037**: **Given** task 1 in `todo`, **When** `todo status 1 todo` runs, **Then** stderr is
    `Error: cannot change status from todo to todo.` and exit code is 1.

- **FR-015**: `done` is final: any status change on a `done` task MUST be rejected. Status values
  MUST be one of `todo`, `in_progress`, `done`.
  - **AC-038**: **Given** task 1 in `done`, **When** `todo status 1 todo`, `todo status 1
    in_progress`, or `todo status 1 done` runs, **Then** each prints to stderr
    `Error: task 1 is done; its status cannot be changed.`, exits with code 1, and task 1 remains
    `done`.
  - **AC-039**: **Given** task 1 in `todo`, **When** `todo status 1 finished` runs, **Then**
    stderr is `Error: status must be one of: todo, in_progress, done.` and exit code is 1.

#### Identifiers

- **FR-016**: Task ids MUST be sequential positive integers starting at 1 and MUST never be reused,
  even after deletions (including deleting all tasks).
  - **AC-040**: **Given** tasks 1, 2, 3, **When** `todo delete 3` then `todo add "Next"` run,
    **Then** the add prints `Added task 4: Next`.
  - **AC-041**: **Given** tasks 1 and 2, **When** both are deleted and `todo add "Fresh"` runs,
    **Then** it prints `Added task 3: Fresh` and the task list is
    `3 | todo | medium | Fresh | tags: - | due: -`.

#### Storage

- **FR-017**: All tasks MUST be saved in a single file named `tasks.json` in the current working
  directory and persist between runs. A missing file means "no tasks"; it is created on the first
  change. Read-only commands (`list`, `--help`) MUST NOT create the file.
  - **AC-042**: **Given** `todo add "Buy milk"` has completed, **When** `todo list` runs as a new
    invocation, **Then** stdout is `1 | todo | medium | Buy milk | tags: - | due: -`.
  - **AC-043**: **Given** no `tasks.json`, **When** `todo list` runs, **Then** stdout is
    `No tasks found.`, exit code is 0, and `tasks.json` still does not exist.

- **FR-018**: If `tasks.json` exists but is corrupt (empty, not valid JSON, or not in the
  expected structure), every command that reads it MUST print
  `Error: tasks.json is corrupt and was not modified. Fix or remove it and try again.` to stderr,
  exit with code 2, and leave the file byte-for-byte unchanged.
  - **AC-044**: **Given** `tasks.json` contains `{not json`, **When** `todo list` or
    `todo add "X"` runs, **Then** stderr is the corrupt-file message above, exit code is 2, and
    the file content is still exactly `{not json`.
  - **AC-045**: **Given** `tasks.json` contains valid JSON with the wrong structure (e.g. `[]`, or
    a task record missing its title), **When** `todo list` runs, **Then** stderr is the
    corrupt-file message, exit code is 2, and the file is unchanged.

- **FR-019**: If saving fails, the previous contents of `tasks.json` MUST remain intact and the
  command MUST print `Error: could not save tasks.json; no changes were made.` to stderr and exit
  with code 2.
  - **AC-046**: **Given** `tasks.json` holds task 1 and the file cannot be written (e.g. the
    location is read-only or the write is interrupted), **When** `todo add "X"` runs, **Then**
    stderr is the save-failure message, exit code is 2, and `tasks.json` is byte-for-byte
    unchanged.

#### General CLI behaviour

- **FR-020**: Invalid usage (unknown command, missing required argument, unknown option) MUST
  print a usage message to stderr and exit with code 1. `todo --help` MUST print usage listing
  all commands to stdout and exit with code 0.
  - **AC-047**: **Given** any state, **When** `todo frobnicate` or `todo add` (no title) runs,
    **Then** stderr contains `usage:`, stdout is empty, and exit code is 1.
  - **AC-048**: **Given** any state, **When** `todo --help` runs, **Then** stdout contains each of
    `add`, `list`, `update`, `delete`, `status`, and exit code is 0.

### Key Entities

- **Task**: one unit of work. Attributes: id (positive integer, unique, never reused), title
  (1–100 characters), status (`todo`, `in_progress`, `done`), priority (`low`, `medium`, `high`),
  tags (ordered set of lower-case tags, possibly empty), due date (calendar date or none).
- **Task store**: the single `tasks.json` file holding all tasks plus the next id to assign, so
  ids are never reused after deletion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of acceptance criteria AC-001 – AC-048 pass as automated tests.
- **SC-002**: Each command completes in under 1 second with 1,000 tasks stored.
- **SC-003**: In every corrupt-file and failed-save scenario, 0 bytes of existing task data are
  lost or altered.
- **SC-004**: A first-time user can add a task, list it, and mark it done using only
  `todo --help` for guidance, in under 2 minutes.
- **SC-005**: Every error message names what was wrong and, where applicable, the allowed values,
  so the user can correct the command without consulting other documentation.

## Assumptions

- Single user, single machine; no concurrent access to `tasks.json` from multiple processes.
- `tasks.json` lives in the current working directory; there is no option to relocate it in v1.
- "done is final" restricts **status** changes only. Title, priority and tags of a `done` task may
  still be edited, and a `done` task may be deleted.
- Changing a task's status to the status it already has is treated as an invalid transition.
- The due date can be set only when adding a task; it cannot be updated or cleared in v1 (the
  request lists only title, priority and tags as updatable).
- Tags are normalised to lower case, and tag filtering is case-insensitive.
- Creation order is the same as id order, since ids are assigned sequentially.
- No reminders, overdue warnings, recurring tasks, search, or colour output in v1.

## Change Log

- 2026-11-13: Initial draft.
