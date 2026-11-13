"""Command-line interface for the Smart Todo CLI (contracts/cli.md).

This is the only module that prints or chooses exit codes:
0 success, 1 user/validation error (including usage errors), 2 storage error.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NoReturn

from todo.models import Task, TodoError
from todo.service import TodoService
from todo.storage import StorageError

TASKS_FILE = "tasks.json"

EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_STORAGE_ERROR = 2


class _Parser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors exit with code 1 instead of 2."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USER_ERROR, f"{self.prog}: error: {message}\n")


# --------------------------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------------------------


def format_task(task: Task) -> str:
    """Format one task as a ``todo list`` line."""
    tags = ",".join(task.tags) if task.tags else "-"
    due = task.due if task.due else "-"
    return (
        f"{task.id} | {task.status.value} | {task.priority.value} | {task.title} | "
        f"tags: {tags} | due: {due}"
    )


# --------------------------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------------------------


def _cmd_add(service: TodoService, args: argparse.Namespace) -> int:
    task = service.add(args.title, priority=args.priority, tags=args.tags, due=args.due)
    print(f"Added task {task.id}: {task.title}")
    return EXIT_OK


def _cmd_list(service: TodoService, args: argparse.Namespace) -> int:
    tasks = service.list_tasks(tag=args.tag, status=args.status)
    if not tasks:
        print("No tasks found.")
    else:
        for task in tasks:
            print(format_task(task))
    return EXIT_OK


def _cmd_update(service: TodoService, args: argparse.Namespace) -> int:
    task = service.update(
        args.id, title=args.title, priority=args.priority, tags=args.tags, due=args.due
    )
    print(f"Updated task {task.id}.")
    return EXIT_OK


def _cmd_delete(service: TodoService, args: argparse.Namespace) -> int:
    task_id = service.delete(args.id)
    print(f"Deleted task {task_id}.")
    return EXIT_OK


def _cmd_status(service: TodoService, args: argparse.Namespace) -> int:
    old, new = service.set_status(args.id, args.new_status)
    # args.id was validated by the service, so int() cannot fail here.
    print(f"Task {int(args.id)} status: {old.value} -> {new.value}")
    return EXIT_OK


Handler = Callable[[TodoService, argparse.Namespace], int]


# --------------------------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for all commands."""
    parser = _Parser(
        prog="todo",
        description="Smart Todo CLI: manage personal tasks stored in ./tasks.json.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p_add = sub.add_parser("add", help="add a new task", description="Add a new task.")
    p_add.add_argument("title", help="task title (1-100 characters)")
    p_add.add_argument("--priority", help="low, medium or high (default: medium)")
    p_add.add_argument("--tags", help="comma-separated tags, e.g. work,urgent")
    p_add.add_argument("--due", help="due date in YYYY-MM-DD format")
    p_add.set_defaults(handler=_cmd_add)

    p_list = sub.add_parser(
        "list", help="list tasks (sorted by priority)", description="List tasks."
    )
    p_list.add_argument("--tag", help="show only tasks with this tag")
    p_list.add_argument("--status", help="show only tasks in this status (todo, in_progress, done)")
    p_list.set_defaults(handler=_cmd_list)

    p_update = sub.add_parser(
        "update", help="change a task's title, priority, tags or due date",
        description="Update a task.",
    )
    p_update.add_argument("id", help="task id")
    p_update.add_argument("--title", help="new title (1-100 characters)")
    p_update.add_argument("--priority", help="low, medium or high")
    p_update.add_argument("--tags", help='comma-separated tags; "" removes all tags')
    p_update.add_argument("--due", help='due date in YYYY-MM-DD format; "" removes it')
    p_update.set_defaults(handler=_cmd_update)

    p_delete = sub.add_parser("delete", help="delete a task", description="Delete a task.")
    p_delete.add_argument("id", help="task id")
    p_delete.set_defaults(handler=_cmd_delete)

    p_status = sub.add_parser(
        "status", help="change a task's status", description="Change a task's status."
    )
    p_status.add_argument("id", help="task id")
    p_status.add_argument("new_status", help="todo, in_progress or done")
    p_status.set_defaults(handler=_cmd_status)

    return parser


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------


def _configure_streams() -> None:
    """Make stdout/stderr UTF-8 so non-ASCII titles never crash output on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError, io.UnsupportedOperation):
            reconfigure(encoding="utf-8", errors="replace")


def _exit_code(code: object) -> int:
    if code is None:
        return EXIT_OK
    if isinstance(code, int):
        return code
    return EXIT_USER_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    _configure_streams()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) or usage error (1)
        return _exit_code(exc.code)

    handler: Handler = args.handler
    service = TodoService(Path(TASKS_FILE))
    try:
        return handler(service, args)
    except StorageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_STORAGE_ERROR
    except TodoError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
