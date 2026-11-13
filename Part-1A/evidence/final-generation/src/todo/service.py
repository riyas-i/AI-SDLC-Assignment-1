"""Business logic for the Smart Todo CLI.

Every operation loads the store first (so a corrupt or unreadable file always wins), then
validates arguments in the order of contracts/cli.md, then looks up the task, applies business
rules and finally saves. Nothing is saved unless every check passes.
"""

from __future__ import annotations

from pathlib import Path

from todo import storage
from todo.models import (
    MSG_NOTHING_TO_UPDATE,
    PRIORITY_RANK,
    NotFoundError,
    Priority,
    Status,
    Task,
    ValidationError,
    check_transition,
    parse_due,
    parse_priority,
    parse_status,
    parse_tags,
    parse_task_id,
    validate_title,
)
from todo.storage import TaskStore


def _find(store: TaskStore, task_id: int) -> Task:
    for task in store.tasks:
        if task.id == task_id:
            return task
    raise NotFoundError(f"task {task_id} not found.")


class TodoService:
    """Task operations backed by a single ``tasks.json`` file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def add(
        self,
        title: str,
        priority: str | None = None,
        tags: str | None = None,
        due: str | None = None,
    ) -> Task:
        """Create a new task and return it."""
        store = storage.load(self.path)

        clean_title = validate_title(title)
        clean_priority = parse_priority(priority) if priority is not None else Priority.MEDIUM
        clean_tags = parse_tags(tags) if tags is not None else []
        clean_due = parse_due(due) if due is not None else None

        task = Task(
            id=store.next_id,
            title=clean_title,
            status=Status.TODO,
            priority=clean_priority,
            tags=clean_tags,
            due=clean_due,
        )
        store.tasks.append(task)
        store.next_id += 1
        storage.save(self.path, store)
        return task

    def list_tasks(self, tag: str | None = None, status: str | None = None) -> list[Task]:
        """Return tasks matching all given filters, sorted by priority then id. Never saves."""
        store = storage.load(self.path)

        wanted_status = parse_status(status) if status is not None else None
        wanted_tag = tag.strip().lower() if tag is not None else None

        tasks = store.tasks
        if wanted_tag is not None:
            tasks = [t for t in tasks if wanted_tag in t.tags]
        if wanted_status is not None:
            tasks = [t for t in tasks if t.status is wanted_status]
        return sorted(tasks, key=lambda t: (PRIORITY_RANK[t.priority], t.id))

    def update(
        self,
        task_id: str,
        title: str | None = None,
        priority: str | None = None,
        tags: str | None = None,
        due: str | None = None,
    ) -> Task:
        """Change the given fields of a task. ``None`` means "not given"."""
        store = storage.load(self.path)

        clean_id = parse_task_id(task_id)
        clean_title = validate_title(title) if title is not None else None
        clean_priority = parse_priority(priority) if priority is not None else None
        clean_tags = parse_tags(tags) if tags is not None else None
        clean_due = parse_due(due) if due is not None else None

        task = _find(store, clean_id)

        if title is None and priority is None and tags is None and due is None:
            raise ValidationError(MSG_NOTHING_TO_UPDATE)

        if clean_title is not None:
            task.title = clean_title
        if clean_priority is not None:
            task.priority = clean_priority
        if clean_tags is not None:
            task.tags = clean_tags
        if due is not None:
            task.due = clean_due

        storage.save(self.path, store)
        return task

    def delete(self, task_id: str) -> int:
        """Delete a task. ``next_id`` is never changed, so ids are not reused."""
        store = storage.load(self.path)

        clean_id = parse_task_id(task_id)
        task = _find(store, clean_id)
        store.tasks.remove(task)

        storage.save(self.path, store)
        return clean_id

    def set_status(self, task_id: str, new_status: str) -> tuple[Status, Status]:
        """Change a task's status; return ``(old, new)``."""
        store = storage.load(self.path)

        clean_id = parse_task_id(task_id)
        clean_status = parse_status(new_status)
        task = _find(store, clean_id)

        old = task.status
        check_transition(clean_id, old, clean_status)
        task.status = clean_status

        storage.save(self.path, store)
        return old, clean_status
