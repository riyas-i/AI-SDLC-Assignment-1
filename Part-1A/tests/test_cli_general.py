"""Acceptance tests for general CLI behaviour (FR-020, AC-047, AC-048)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from conftest import SRC_DIR

COMMANDS = ("add", "list", "update", "delete", "status")


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["frobnicate"], id="unknown-command"),
        pytest.param(["add"], id="add-without-title"),
        pytest.param(["list", "--bogus"], id="unknown-option"),
        pytest.param([], id="no-command"),
    ],
)
def test_ac047_unknown_command_usage_exit1(run, store_path, args):
    """AC-047: Given any state, When `todo frobnicate` or `todo add` (no title) runs, Then
    stderr contains `usage:`, stdout is empty, and exit code is 1.

    FR-020 also covers unknown options and a missing command."""
    result = run(*args)
    assert result.code == 1
    assert result.out == ""
    assert "usage:" in result.err
    assert not store_path.exists()


def test_ac048_help_lists_commands(run, store_path):
    """AC-048: Given any state, When `todo --help` runs, Then stdout contains each of `add`,
    `list`, `update`, `delete`, `status`, and exit code is 0."""
    result = run("--help")
    assert result.code == 0
    assert result.err == ""
    for command in COMMANDS:
        assert command in result.out
    assert not store_path.exists()  # FR-017: --help never creates tasks.json


def test_ac048_python_m_todo_help_subprocess(tmp_path):
    """AC-048 (end to end): `python -m todo --help` in a real process prints every command to
    stdout and exits 0."""
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    proc = subprocess.run(
        [sys.executable, "-m", "todo", "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "usage:" in proc.stdout
    for command in COMMANDS:
        assert command in proc.stdout
    assert not (tmp_path / "tasks.json").exists()
