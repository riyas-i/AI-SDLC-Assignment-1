# Contract: `tasks.json` File Format

- Location: `tasks.json` in the current working directory.
- Encoding: UTF-8, no BOM. Written with `json.dumps(..., ensure_ascii=False, indent=2)` plus a
  trailing newline.
- Writes are atomic: temp file in the same directory → `fsync` → `os.replace`.

## Schema (version 1)

```json
{
  "version": 1,
  "next_id": 4,
  "tasks": [
    {
      "id": 1,
      "title": "Buy milk",
      "status": "todo",
      "priority": "medium",
      "tags": ["home", "errand"],
      "due": "2026-12-01"
    },
    {
      "id": 3,
      "title": "File taxes",
      "status": "done",
      "priority": "high",
      "tags": [],
      "due": null
    }
  ]
}
```

## Validity rules (any violation → corrupt, exit 2, file untouched)

1. The bytes decode as UTF-8 and parse as JSON. An empty file is corrupt.
2. The top level is an object with exactly the keys `version`, `next_id` and `tasks`. Any extra
   key is corrupt (FR-018, AC-045), so unknown data is never silently dropped on save.
3. `version` is exactly the integer `1`.
4. `next_id` is an integer (not a bool) and ≥ 1.
5. `tasks` is a list. Each element is an object with exactly the six keys `id`, `title`,
   `status`, `priority`, `tags`, `due` (no extra keys), where:
   - `id`: integer (not a bool), ≥ 1, unique across tasks, `< next_id`
   - `title`: string, equal to its own `strip()`, length 1–100
   - `status`: one of `todo`, `in_progress`, `done`
   - `priority`: one of `low`, `medium`, `high`
   - `tags`: list of unique strings, each matching `^[a-z0-9_-]{1,30}$`
   - `due`: `null` or a string that is a real date in `YYYY-MM-DD` form

## Missing file

Treated as `{"version": 1, "next_id": 1, "tasks": []}`. It is created only by a command that
changes data (`add`, `update`, `delete`, `status`), never by `list` or `--help` (AC-043).
