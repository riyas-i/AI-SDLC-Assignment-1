"""Loading and atomic saving of ``tasks.json`` (contracts/tasks-file.md)."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from todo.models import Priority, Status, Task, is_valid_due, is_valid_tag

STORE_VERSION = 1
TITLE_MAX_LENGTH = 100

MSG_CORRUPT = "tasks.json is corrupt and was not modified. Fix or remove it and try again."
MSG_READ = "could not read tasks.json."
MSG_SAVE = "could not save tasks.json; no changes were made."

_TOP_LEVEL_KEYS = frozenset({"version", "next_id", "tasks"})
_TASK_KEYS = frozenset({"id", "title", "status", "priority", "tags", "due"})
_STATUS_VALUES = frozenset(s.value for s in Status)
_PRIORITY_VALUES = frozenset(p.value for p in Priority)


class StorageError(Exception):
    """A problem reading or writing ``tasks.json`` (exit code 2)."""

    def __init__(self, message: str = MSG_READ) -> None:
        super().__init__(message)


class CorruptStoreError(StorageError):
    """``tasks.json`` exists but is not a valid task store."""

    def __init__(self, message: str = MSG_CORRUPT) -> None:
        super().__init__(message)


class SaveError(StorageError):
    """Writing or replacing ``tasks.json`` failed; the old file is intact."""

    def __init__(self, message: str = MSG_SAVE) -> None:
        super().__init__(message)


@dataclass
class TaskStore:
    """In-memory form of the whole ``tasks.json`` file."""

    version: int = STORE_VERSION
    next_id: int = 1
    tasks: list[Task] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready representation."""
        return {
            "version": self.version,
            "next_id": self.next_id,
            "tasks": [task.to_dict() for task in self.tasks],
        }


# --------------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------------


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_task(raw: object, next_id: int, seen_ids: set[int]) -> Task:
    if not isinstance(raw, dict) or set(raw.keys()) != _TASK_KEYS:
        raise CorruptStoreError()

    task_id = raw["id"]
    if not _is_int(task_id) or task_id < 1 or task_id >= next_id or task_id in seen_ids:
        raise CorruptStoreError()

    title = raw["title"]
    if (
        not isinstance(title, str)
        or title != title.strip()
        or not 1 <= len(title) <= TITLE_MAX_LENGTH
    ):
        raise CorruptStoreError()

    status = raw["status"]
    if not isinstance(status, str) or status not in _STATUS_VALUES:
        raise CorruptStoreError()

    priority = raw["priority"]
    if not isinstance(priority, str) or priority not in _PRIORITY_VALUES:
        raise CorruptStoreError()

    tags = raw["tags"]
    if not isinstance(tags, list):
        raise CorruptStoreError()
    for tag in tags:
        if not isinstance(tag, str) or not is_valid_tag(tag):
            raise CorruptStoreError()
    if len(set(tags)) != len(tags):
        raise CorruptStoreError()

    due = raw["due"]
    if due is not None and (not isinstance(due, str) or not is_valid_due(due)):
        raise CorruptStoreError()

    seen_ids.add(task_id)
    return Task.from_dict(raw)


def _validate_store(data: object) -> TaskStore:
    if not isinstance(data, dict) or set(data.keys()) != _TOP_LEVEL_KEYS:
        raise CorruptStoreError()

    version = data["version"]
    if not _is_int(version) or version != STORE_VERSION:
        raise CorruptStoreError()

    next_id = data["next_id"]
    if not _is_int(next_id) or next_id < 1:
        raise CorruptStoreError()

    raw_tasks = data["tasks"]
    if not isinstance(raw_tasks, list):
        raise CorruptStoreError()

    seen_ids: set[int] = set()
    tasks = [_validate_task(raw, next_id, seen_ids) for raw in raw_tasks]
    return TaskStore(version=version, next_id=next_id, tasks=tasks)


def load(path: Path) -> TaskStore:
    """Load the task store from ``path``.

    A missing file yields an empty store (the file is not created). A file that cannot be read
    raises ``StorageError``; a file that is not a valid store raises ``CorruptStoreError``.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return TaskStore()
    except OSError as exc:
        raise StorageError(MSG_READ) from exc

    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise CorruptStoreError() from exc

    return _validate_store(data)


# --------------------------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------------------------


def save(path: Path, store: TaskStore) -> None:
    """Atomically write ``store`` to ``path`` (temp file in same dir, fsync, ``os.replace``).

    On any failure the temp file is removed, the original file is left untouched and
    ``SaveError`` is raised.
    """
    payload = (json.dumps(store.to_dict(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    directory = path.parent if str(path.parent) else Path(".")
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=".tasks-", suffix=".tmp")
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise SaveError() from exc
