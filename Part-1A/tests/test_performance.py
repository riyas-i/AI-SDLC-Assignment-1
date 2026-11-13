"""SC-002: each command completes in under 1 second with 1,000 tasks stored, measured both
in-process and end to end (including interpreter start-up)."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from conftest import SRC_DIR

N_TASKS = 1000
LIMIT_SECONDS = 1.0
PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in_progress", "done")


def _seed(write_store):
    tasks = [
        {
            "id": i,
            "title": f"Task number {i}",
            "priority": PRIORITIES[i % 3],
            "status": STATUSES[i % 3],
            "tags": ["work"] if i % 2 else ["home", "bills"],
            "due": "2026-12-01" if i % 5 == 0 else None,
        }
        for i in range(1, N_TASKS + 1)
    ]
    return write_store(tasks, next_id=N_TASKS + 1)


def test_sc002_list_and_add_with_1000_tasks_under_1s(run, write_store):
    """SC-002 (in-process): `todo list` and `todo add` each finish in < 1 s with 1,000
    tasks."""
    _seed(write_store)

    start = time.perf_counter()
    listed = run("list")
    list_seconds = time.perf_counter() - start
    assert listed.code == 0
    assert len(listed.out.splitlines()) == N_TASKS
    assert list_seconds < LIMIT_SECONDS, f"list took {list_seconds:.3f}s"

    start = time.perf_counter()
    added = run("add", "One more")
    add_seconds = time.perf_counter() - start
    assert added == (0, f"Added task {N_TASKS + 1}: One more\n", "")
    assert add_seconds < LIMIT_SECONDS, f"add took {add_seconds:.3f}s"


def _timed_cli(cwd, *args):
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "todo", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    return proc, time.perf_counter() - start


def test_sc002_end_to_end_subprocess_under_1s(write_store, cli_env):
    """SC-002 (end to end): `python -m todo list` and `python -m todo add` each finish in
    < 1 s with 1,000 tasks, including interpreter start-up."""
    _seed(write_store)

    proc, seconds = _timed_cli(cli_env, "list")
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.splitlines()) == N_TASKS
    assert seconds < LIMIT_SECONDS, f"list took {seconds:.3f}s"

    proc, seconds = _timed_cli(cli_env, "add", "One more")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"Added task {N_TASKS + 1}: One more\n"
    assert seconds < LIMIT_SECONDS, f"add took {seconds:.3f}s"
