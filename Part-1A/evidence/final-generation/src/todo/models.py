"""Domain types and validators for the Smart Todo CLI.

This module is pure: it performs no I/O. Validators raise ``ValidationError`` with the exact
message texts from ``contracts/cli.md`` (without the ``Error: `` prefix, which the CLI adds).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

# --------------------------------------------------------------------------------------------
# Messages (contracts/cli.md)
# --------------------------------------------------------------------------------------------

MSG_TITLE = "title must be 1-100 characters."
MSG_PRIORITY = "priority must be one of: low, medium, high."
MSG_TAG = "each tag must be 1-30 characters using only letters, digits, '-' or '_'."
MSG_DUE = "due date must be a valid date in YYYY-MM-DD format."
MSG_STATUS = "status must be one of: todo, in_progress, done."
MSG_TASK_ID = "task id must be a positive integer."
MSG_NOTHING_TO_UPDATE = "nothing to update; provide --title, --priority, --tags or --due."

TITLE_MAX_LENGTH = 100

_TAG_RE = re.compile(r"[a-z0-9_-]{1,30}")
_DUE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_ID_RE = re.compile(r"[0-9]+")


# --------------------------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------------------------


class Status(StrEnum):
    """Lifecycle state of a task."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Priority(StrEnum):
    """Task priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


PRIORITY_RANK: dict[Priority, int] = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}

ALLOWED_TRANSITIONS: frozenset[tuple[Status, Status]] = frozenset(
    {
        (Status.TODO, Status.IN_PROGRESS),
        (Status.IN_PROGRESS, Status.DONE),
        (Status.TODO, Status.DONE),
    }
)


# --------------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------------


class TodoError(Exception):
    """Base class for domain errors."""


class ValidationError(TodoError):
    """Invalid user input or a broken business rule (exit code 1)."""


class NotFoundError(ValidationError):
    """The requested task id does not exist (exit code 1)."""


# --------------------------------------------------------------------------------------------
# Task entity
# --------------------------------------------------------------------------------------------


@dataclass
class Task:
    """One unit of work."""

    id: int
    title: str
    status: Status = Status.TODO
    priority: Priority = Priority.MEDIUM
    tags: list[str] = field(default_factory=list)
    due: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready representation (contracts/tasks-file.md)."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "tags": list(self.tags),
            "due": self.due,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Build a task from an already-validated mapping."""
        return cls(
            id=data["id"],
            title=data["title"],
            status=Status(data["status"]),
            priority=Priority(data["priority"]),
            tags=list(data["tags"]),
            due=data["due"],
        )


# --------------------------------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------------------------------


def validate_title(title: str) -> str:
    """Return the trimmed title if it is 1-100 characters long."""
    stripped = title.strip()
    if not 1 <= len(stripped) <= TITLE_MAX_LENGTH:
        raise ValidationError(MSG_TITLE)
    return stripped


def parse_priority(value: str) -> Priority:
    """Parse a priority case-insensitively."""
    try:
        return Priority(value.lower())
    except ValueError:
        raise ValidationError(MSG_PRIORITY) from None


def is_valid_tag(tag: str) -> bool:
    """Return True if ``tag`` is a stored-form (lower-case) valid tag."""
    return _TAG_RE.fullmatch(tag) is not None


def parse_tags(value: str) -> list[str]:
    """Parse a comma-separated tag list: trim, lower-case, drop empties, de-duplicate."""
    tags: list[str] = []
    for part in value.split(","):
        tag = part.strip().lower()
        if not tag:
            continue
        if not is_valid_tag(tag):
            raise ValidationError(MSG_TAG)
        if tag not in tags:
            tags.append(tag)
    return tags


def is_valid_due(value: str) -> bool:
    """Return True if ``value`` is a real calendar date in strict ``YYYY-MM-DD`` form."""
    if _DUE_RE.fullmatch(value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def parse_due(value: str) -> str | None:
    """Parse a due date. ``""`` means "no due date" and returns ``None``."""
    if value == "":
        return None
    if not is_valid_due(value):
        raise ValidationError(MSG_DUE)
    return value


def parse_status(value: str) -> Status:
    """Parse a status value (exact, lower-case)."""
    try:
        return Status(value)
    except ValueError:
        raise ValidationError(MSG_STATUS) from None


def parse_task_id(value: str) -> int:
    """Parse a task id; it must be a positive integer written with ASCII digits."""
    if _ID_RE.fullmatch(value) is None:
        raise ValidationError(MSG_TASK_ID)
    task_id = int(value)
    if task_id < 1:
        raise ValidationError(MSG_TASK_ID)
    return task_id


def check_transition(task_id: int, old: Status, new: Status) -> None:
    """Raise ``ValidationError`` unless ``old -> new`` is an allowed status change."""
    if old is Status.DONE:
        raise ValidationError(f"task {task_id} is done; its status cannot be changed.")
    if (old, new) not in ALLOWED_TRANSITIONS:
        raise ValidationError(f"cannot change status from {old.value} to {new.value}.")
