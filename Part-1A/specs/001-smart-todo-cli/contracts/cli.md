# Contract: Command-Line Interface

Invocation: `todo <command> ...` (console script) or `python -m todo <command> ...`.
All behaviour below is normative. The message texts are copied from the spec and must match
exactly.

## Grammar

```text
todo --help
todo add <title> [--priority P] [--tags T] [--due D]
todo list [--tag TAG] [--status S]
todo update <id> [--title TITLE] [--priority P] [--tags T] [--due D]
todo delete <id>
todo status <id> <new_status>
```

- `<id>`, `P`, `S` and `<new_status>` are accepted by argparse as plain strings and validated by
  the application (so the exact messages below apply).
- `T` is a comma-separated list; `""` means "no tags" (on `update`: clear the tags).
- `D` is `YYYY-MM-DD`; `""` on `update` clears the due date.

## Streams and exit codes

| Outcome | stdout | stderr | Exit |
|---------|--------|--------|------|
| Success | message or list | empty | 0 |
| Validation / user error | empty | `Error: <message>` | 1 |
| argparse usage error | empty | usage + `todo: error: ...` | 1 |
| Storage error | empty | `Error: <message>` | 2 |
| `--help` | usage listing all commands | empty | 0 |

## Success output

| Command | stdout |
|---------|--------|
| `add` | `Added task <id>: <title>` (title as stored, i.e. trimmed) |
| `list` (no matches) | `No tasks found.` |
| `list` | one line per task: `<id> \| <status> \| <priority> \| <title> \| tags: <t1,t2 or -> \| due: <YYYY-MM-DD or ->` |
| `update` | `Updated task <id>.` |
| `delete` | `Deleted task <id>.` |
| `status` | `Task <id> status: <old> -> <new>` |

## Error messages (stderr; each followed by a newline)

| Condition | Message | Exit |
|-----------|---------|------|
| Title empty, blank or > 100 chars | `Error: title must be 1-100 characters.` | 1 |
| Bad priority | `Error: priority must be one of: low, medium, high.` | 1 |
| Bad tag | `Error: each tag must be 1-30 characters using only letters, digits, '-' or '_'.` | 1 |
| Bad due date | `Error: due date must be a valid date in YYYY-MM-DD format.` | 1 |
| Bad status value (`list --status`, `status`) | `Error: status must be one of: todo, in_progress, done.` | 1 |
| Id not a positive integer | `Error: task id must be a positive integer.` | 1 |
| Id not found | `Error: task <id> not found.` | 1 |
| `update` with no fields | `Error: nothing to update; provide --title, --priority, --tags or --due.` | 1 |
| Illegal transition (from `todo` / `in_progress`) | `Error: cannot change status from <old> to <new>.` | 1 |
| Any transition from `done` | `Error: task <id> is done; its status cannot be changed.` | 1 |
| Corrupt `tasks.json` | `Error: tasks.json is corrupt and was not modified. Fix or remove it and try again.` | 2 |
| Save failed | `Error: could not save tasks.json; no changes were made.` | 2 |
| Read failed, e.g. access denied (FR-018, AC-055) | `Error: could not read tasks.json.` | 2 |

## Check order (determines which error wins)

1. argparse structure (usage error → 1)
2. Load `tasks.json` (corrupt / unreadable → 2)
3. Validate the id format, then the field values in the order title, priority, tags, due, status
   (→ 1)
4. Look up the id (not found → 1)
5. Business rules: nothing-to-update, status transition (→ 1)
6. Save (failure → 2)
