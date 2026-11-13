"""Unit tests for ``todo.storage`` (contracts/tasks-file.md, research.md R1/R2;
FR-017 – FR-019).

Attributes are looked up on the module at call time so each test fails on its own until the
implementation exists.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest
from conftest import make_task

from todo import models, storage

CORRUPT_MSG = "tasks.json is corrupt and was not modified. Fix or remove it and try again."
READ_MSG = "could not read tasks.json."
SAVE_MSG = "could not save tasks.json; no changes were made."


@pytest.fixture
def path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "tasks.json"


def _store_bytes(next_id=2, tasks=None, **top) -> bytes:
    data = {
        "version": 1,
        "next_id": next_id,
        "tasks": [make_task(1, "Buy milk")] if tasks is None else tasks,
    }
    data.update(top)
    return json.dumps(data).encode("utf-8")


# --- Error hierarchy -----------------------------------------------------------------------


def test_unit_storage_error_hierarchy():
    assert issubclass(storage.CorruptStoreError, storage.StorageError)
    assert issubclass(storage.SaveError, storage.StorageError)


# --- load ----------------------------------------------------------------------------------


def test_ac043_load_missing_file_is_empty_and_not_created(path):
    store = storage.load(path)
    assert store.version == 1
    assert store.next_id == 1
    assert store.tasks == []
    assert not path.exists()


def test_unit_load_valid_file(path):
    path.write_bytes(
        _store_bytes(
            next_id=5,
            tasks=[
                make_task(1, "Buy milk", tags=["home"], due="2026-12-01"),
                make_task(3, "File taxes", status="done", priority="high"),
            ],
        )
    )
    store = storage.load(path)
    assert store.next_id == 5
    assert [t.id for t in store.tasks] == [1, 3]
    assert store.tasks[0].tags == ["home"]
    assert store.tasks[0].due == "2026-12-01"
    assert store.tasks[1].status == models.Status.DONE
    assert store.tasks[1].priority == models.Priority.HIGH


def _task_with(**changes):
    task = make_task(1, "Buy milk")
    task.update(changes)
    return task


def _task_without(key):
    task = make_task(1, "Buy milk")
    del task[key]
    return task


CORRUPT_CASES = [
    # Rule 1: UTF-8 + JSON
    pytest.param(b"", id="r1-empty"),
    pytest.param(b"{not json", id="r1-not-json"),
    pytest.param(b"\xff\xfe\x00{", id="r1-not-utf8"),
    # Rule 2: top level is an object with exactly version/next_id/tasks
    pytest.param(b"[]", id="r2-list"),
    pytest.param(b"null", id="r2-null"),
    pytest.param(b'{"version": 1, "next_id": 1}', id="r2-missing-tasks"),
    pytest.param(_store_bytes(notes="x"), id="r2-extra-top-key"),
    # Rule 3: version is exactly the integer 1
    pytest.param(_store_bytes(version=2), id="r3-version-2"),
    pytest.param(_store_bytes(version="1"), id="r3-version-str"),
    pytest.param(_store_bytes(version=True), id="r3-version-bool"),
    # Rule 4: next_id is an int (not bool) >= 1
    pytest.param(_store_bytes(next_id=0, tasks=[]), id="r4-next-id-0"),
    pytest.param(_store_bytes(next_id=True, tasks=[]), id="r4-next-id-bool"),
    pytest.param(_store_bytes(next_id="2"), id="r4-next-id-str"),
    # Rule 5: tasks list and each task record
    pytest.param(_store_bytes(tasks={}), id="r5-tasks-not-list"),
    pytest.param(_store_bytes(tasks=["x"]), id="r5-task-not-object"),
    pytest.param(_store_bytes(tasks=[_task_without("title")]), id="r5-missing-title"),
    pytest.param(_store_bytes(tasks=[_task_without("due")]), id="r5-missing-due"),
    pytest.param(_store_bytes(tasks=[_task_with(notes="x")]), id="r5-extra-task-key"),
    pytest.param(_store_bytes(tasks=[_task_with(id=True)]), id="r5-id-bool"),
    pytest.param(_store_bytes(tasks=[_task_with(id=0)]), id="r5-id-0"),
    pytest.param(_store_bytes(tasks=[_task_with(id="1")]), id="r5-id-str"),
    pytest.param(
        _store_bytes(next_id=3, tasks=[make_task(1, "A"), make_task(1, "B")]),
        id="r5-duplicate-ids",
    ),
    pytest.param(_store_bytes(next_id=1), id="r5-id-not-below-next-id"),
    pytest.param(_store_bytes(tasks=[_task_with(title=5)]), id="r5-title-not-str"),
    pytest.param(_store_bytes(tasks=[_task_with(title="")]), id="r5-title-empty"),
    pytest.param(_store_bytes(tasks=[_task_with(title=" x ")]), id="r5-title-untrimmed"),
    pytest.param(_store_bytes(tasks=[_task_with(title="a" * 101)]), id="r5-title-too-long"),
    pytest.param(_store_bytes(tasks=[_task_with(status="finished")]), id="r5-bad-status"),
    pytest.param(_store_bytes(tasks=[_task_with(priority="urgent")]), id="r5-bad-priority"),
    pytest.param(_store_bytes(tasks=[_task_with(priority="HIGH")]), id="r5-priority-not-lower"),
    pytest.param(_store_bytes(tasks=[_task_with(tags="home")]), id="r5-tags-not-list"),
    pytest.param(_store_bytes(tasks=[_task_with(tags=["Home"])]), id="r5-tag-upper"),
    pytest.param(_store_bytes(tasks=[_task_with(tags=["bad tag"])]), id="r5-tag-invalid"),
    pytest.param(_store_bytes(tasks=[_task_with(tags=[1])]), id="r5-tag-not-str"),
    pytest.param(_store_bytes(tasks=[_task_with(tags=["a", "a"])]), id="r5-tags-duplicate"),
    pytest.param(_store_bytes(tasks=[_task_with(due="2026-02-30")]), id="r5-due-impossible"),
    pytest.param(_store_bytes(tasks=[_task_with(due="2026-1-1")]), id="r5-due-format"),
    pytest.param(_store_bytes(tasks=[_task_with(due=20261201)]), id="r5-due-not-str"),
]


@pytest.mark.parametrize("content", CORRUPT_CASES)
def test_ac045_load_rejects_corrupt_file(path, content):
    path.write_bytes(content)
    with pytest.raises(storage.CorruptStoreError) as excinfo:
        storage.load(path)
    assert str(excinfo.value) == CORRUPT_MSG
    assert path.read_bytes() == content


def test_ac055_load_permission_error_is_storage_error(path, monkeypatch):
    path.write_bytes(_store_bytes())

    def raiser(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(pathlib.Path, "read_bytes", raiser)
    with pytest.raises(storage.StorageError) as excinfo:
        storage.load(path)
    assert not isinstance(excinfo.value, storage.CorruptStoreError)
    assert str(excinfo.value) == READ_MSG


def test_ac055_load_directory_is_storage_error(path):
    """A real non-ENOENT read failure: `tasks.json` is a directory."""
    path.mkdir()
    with pytest.raises(storage.StorageError) as excinfo:
        storage.load(path)
    assert not isinstance(excinfo.value, storage.CorruptStoreError)
    assert str(excinfo.value) == READ_MSG


# --- save ----------------------------------------------------------------------------------


def _sample_store():
    task = models.Task(
        id=1,
        title="Café ☕",
        status=models.Status.TODO,
        priority=models.Priority.HIGH,
        tags=["home", "bills"],
        due="2026-12-01",
    )
    return storage.TaskStore(version=1, next_id=4, tasks=[task])


def test_unit_save_load_round_trip_utf8(path):
    store = _sample_store()
    storage.save(path, store)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    assert "Café ☕" in text  # ensure_ascii=False
    assert text.endswith("\n")
    assert not raw.startswith(b"\xef\xbb\xbf")  # no BOM
    assert json.loads(text) == {
        "version": 1,
        "next_id": 4,
        "tasks": [
            {
                "id": 1,
                "title": "Café ☕",
                "status": "todo",
                "priority": "high",
                "tags": ["home", "bills"],
                "due": "2026-12-01",
            }
        ],
    }
    assert storage.load(path) == store


def test_unit_save_overwrites_existing_file(path):
    path.write_bytes(_store_bytes())
    storage.save(path, _sample_store())
    assert storage.load(path).next_id == 4


def test_unit_save_leaves_no_temp_files(path):
    storage.save(path, _sample_store())
    assert sorted(p.name for p in path.parent.iterdir()) == ["tasks.json"]


def test_ac046_save_failure_raises_and_cleans_up(path, monkeypatch):
    original = _store_bytes()
    path.write_bytes(original)

    def raiser(*args, **kwargs):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(os, "replace", raiser)
    with pytest.raises(storage.SaveError) as excinfo:
        storage.save(path, _sample_store())
    assert str(excinfo.value) == SAVE_MSG
    assert path.read_bytes() == original
    assert list(path.parent.glob(".tasks-*.tmp")) == []
