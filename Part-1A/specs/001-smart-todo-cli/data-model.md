# Data Model: Smart Todo CLI

## Enumerations

| Enum | Values (stored form) | Notes |
|------|----------------------|-------|
| `Status` | `todo`, `in_progress`, `done` | Input is exact (lower-case) |
| `Priority` | `low`, `medium`, `high` | Input is case-insensitive and stored lower-case. Sort rank: high = 0, medium = 1, low = 2 |

## Entity: Task

| Field | Type | Required | Rules | Source |
|-------|------|----------|-------|--------|
| `id` | int | yes | ≥ 1, unique, assigned from `TaskStore.next_id`, never reused | FR-001, FR-016 |
| `title` | str | yes | Stored trimmed; 1–100 characters after `strip()` | FR-002 |
| `status` | `Status` | yes | New tasks start at `todo`; changes follow the state machine below | FR-001, FR-013–FR-015 |
| `priority` | `Priority` | yes | Default `medium` | FR-003 |
| `tags` | list[str] | yes (may be empty) | Each tag is trimmed, lower-cased and matches `^[a-z0-9_-]{1,30}$` (letters/digits checked after lower-casing); empty entries dropped; de-duplicated keeping first order | FR-004 |
| `due` | str \| None | no | `YYYY-MM-DD` and a real calendar date (`date.fromisoformat` plus a strict regex `^\d{4}-\d{2}-\d{2}$`); past dates allowed | FR-005, FR-010 |

**Tag parsing** (`--tags` value): split on `,`, then for each part `strip().lower()`, skip if
empty, reject if it fails the pattern, and skip duplicates. `""` → `[]`.

**Tag filtering**: `list --tag X` matches when `X.strip().lower()` is in `task.tags`.

**Due parsing**: `""` → `None`, only allowed on `update` (clears the date). On `add`, `--due ""`
is treated as "no due date".

## Entity: TaskStore (the `tasks.json` file)

| Field | Type | Rules |
|-------|------|-------|
| `version` | int | Always `1` |
| `next_id` | int | ≥ 1 and greater than every task id |
| `tasks` | list[Task] | Ids unique. File order is insertion order (ascending id) |

Missing file → `TaskStore(version=1, next_id=1, tasks=[])`, which is not written until a change
is made. Full on-disk schema and corruption rules: [contracts/tasks-file.md](contracts/tasks-file.md).

## Status state machine

```text
        ┌──────────────┐
        │              ▼
  todo ──► in_progress ──► done   (done is terminal)
    └────────────────────►
```

| From \ To | `todo` | `in_progress` | `done` |
|-----------|--------|---------------|--------|
| `todo` | ✗ (AC-037) | ✓ (AC-033) | ✓ (AC-035) |
| `in_progress` | ✗ (AC-036) | ✗ | ✓ (AC-034) |
| `done` | ✗ (AC-038) | ✗ (AC-038) | ✗ (AC-038) |

- A rejected change from `todo` or `in_progress` gives
  `cannot change status from <old> to <new>.`
- Any change from `done` gives `task <id> is done; its status cannot be changed.`
- Editing the title, priority, tags or due date, and deleting, are allowed in **every** status,
  including `done` (AC-049, AC-050).

## Ordering

`list` output is sorted by `(priority_rank, id)`. Since ids are assigned in creation order,
this gives "high → medium → low, ties in creation order" (FR-007). Filters (`--tag`,
`--status`) are applied before sorting and combine with AND.

## Error types → exit codes

| Exception (module) | Meaning | Exit |
|--------------------|---------|------|
| `ValidationError` (models) | Bad title, priority, tags, due, status, id format, nothing to update, illegal transition | 1 |
| `NotFoundError(ValidationError)` (models) | Task id does not exist | 1 |
| `CorruptStoreError(StorageError)` (storage) | File exists but is corrupt | 2 |
| `SaveError(StorageError)` (storage) | Writing or replacing the file failed | 2 |
| `StorageError` (storage) | Other read failure | 2 |
| argparse usage error | Unknown command or option, missing argument | 1 |
