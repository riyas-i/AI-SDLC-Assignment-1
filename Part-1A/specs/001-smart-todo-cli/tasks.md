---

description: "Task list for Smart Todo CLI"
---

# Tasks: Smart Todo CLI

**Input**: Design documents from `specs/001-smart-todo-cli/` (plan.md, spec.md, research.md,
data-model.md, contracts/cli.md, contracts/tasks-file.md, quickstart.md)

**Prerequisites**: plan.md, spec.md, constitution v1.1.0 (`.specify/memory/constitution.md`)

**Tests**: Required (constitution Principle III, plus the user's request). Tests are written
**before** any implementation code and must fail first.

**Organization**: The user asked for five phases: Setup → Tests → Harness → Implementation →
Final run. Within each phase, tasks carry a user-story label so each story's tests and code can
be traced:

| Label | User story (spec.md) | ACs |
|-------|----------------------|-----|
| US1 | Capture and see tasks (P1, MVP) | AC-001 – AC-018, AC-047, AC-048 |
| US2 | Track progress through statuses (P2) | AC-033 – AC-039, AC-049 – AC-051 |
| US3 | Filter the list (P3) | AC-019 – AC-024 |
| US4 | Edit and remove tasks (P3) | AC-025 – AC-032, AC-040, AC-041, AC-052 – AC-054 |
| US5 | Data is safe (P2) | AC-042 – AC-046, AC-055 |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story the task belongs to (US1 – US5); Setup/Harness/Final tasks have none
- Every task ends with **Covers:** listing the FR/AC/SC ids (or constitution principles) it
  serves

## Path Conventions

Single project rooted at `Part-1A/`: `src/todo/`, `tests/`, `.harness/`, `evidence/`. All shell
commands are PowerShell, run from `Part-1A/` with `.venv` activated
(`.\.venv\Scripts\Activate.ps1`).

## Ground rules (constitution VII; apply to every task)

- Never weaken an acceptance criterion, delete or skip (`skip`/`xfail`) a failing test, or relax
  Ruff/Bandit/coverage settings to get green. Fix the code instead.
- If a test turns out to contradict `spec.md`, stop and change `spec.md` first, with a dated
  Change Log entry. Only then adjust the test.
- Install packages only with `uv pip install --system-certs ...`. **Never use plain `pip`**: this
  network needs `--system-certs`.
- Commit and push on the current branch after each phase (CLAUDE.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project configuration, empty package skeleton, dev tools installed.

- [X] T001 Create `pyproject.toml` at `Part-1A/pyproject.toml` per research.md R9:
  `[build-system]` setuptools; `[project]` `name = "smart-todo"`, `version = "1.0.0"`,
  `requires-python = ">=3.12"`, `dependencies = []`;
  `[project.optional-dependencies] dev = ["ruff", "bandit", "pytest", "pytest-cov"]`;
  `[project.scripts] todo = "todo.cli:main"`; `[tool.setuptools.packages.find] where = ["src"]`;
  `[tool.pytest.ini_options] pythonpath = ["src"]`, `testpaths = ["tests"]`;
  `[tool.ruff] target-version = "py312"`, `line-length = 100`;
  `[tool.ruff.lint] select = ["E", "F", "W", "I", "B", "UP", "SIM"]`.
  Covers: constitution I, III, IV; FR-020 (`todo` command name).
- [X] T002 [P] Create the package skeleton with empty, importable modules (docstring only, no
  logic): `src/todo/__init__.py`, `src/todo/__main__.py`, `src/todo/models.py`,
  `src/todo/storage.py`, `src/todo/service.py`, `src/todo/cli.py`; and a `tests/` folder (no
  `tests/__init__.py`; pytest finds `src` via `pythonpath`). Covers: plan.md structure.
- [X] T003 [P] Add `Part-1A/.gitignore` ignoring `__pycache__/`, `*.egg-info/`,
  `.pytest_cache/`, `.ruff_cache/`, `.coverage`, `build/`, and `/tasks.json` (a stray data file
  in the project root). `evidence/` must **not** be ignored. Covers: constitution V (data file
  not committed by accident).
- [X] T004 Install the package and dev tools into `.venv`:
  `uv pip install --system-certs -e ".[dev]"`. Then verify with `python -m ruff --version`,
  `python -m bandit --version`, `python -m pytest --version` and
  `python -c "import todo"`. Depends on T001, T002. Covers: constitution IV, IX.
- [x] T005 [P] (Done 2026-11-13 while fixing /speckit-analyze finding I1.) Replace the install command in `specs/001-smart-todo-cli/quickstart.md` (§1) and
  `specs/001-smart-todo-cli/research.md` (R9) with
  `uv pip install --system-certs -e ".[dev]"`, adding a note to never use plain pip.
  Covers: constitution IX (documented commands are valid for this environment).

**Checkpoint**: `python -c "import todo"` works; ruff, bandit and pytest are installed. Commit.

---

## Phase 2: Tests First (spec-derived, must FAIL before Phase 4)

**Purpose**: Encode every acceptance criterion as pytest tests named `test_acNNN_<desc>`. Each
test's docstring quotes its Given/When/Then from spec.md. Expected outputs and exit codes are
copied **verbatim** from spec.md / contracts/cli.md.

**Shared test conventions** (T006 provides them):
- Fixture `cli_env` (autouse in CLI test modules): `monkeypatch.chdir(tmp_path)`; returns
  `tmp_path`.
- Helper `run(*args) -> Result(code, out, err)` calls `todo.cli.main(list(args))` and reads
  `capsys`. `out` and `err` keep their trailing newline; assert with exact strings such as
  `"Added task 1: Buy milk\n"`.
- Helper `write_store(path, tasks, next_id)` writes a valid tasks.json (schema in
  contracts/tasks-file.md) to set up Given-states directly, e.g. a task already `done`.
- Helper `list_lines()` runs `todo list` and returns stdout lines.

- [X] T006 Create `tests/conftest.py` with the `cli_env` fixture and the `run`, `write_store`
  and `list_lines` helpers described above. Covers: all ACs (test infrastructure).
- [X] T007 [P] [US1] Write `tests/test_cli_add.py`: `test_ac001_add_first_task` …
  `test_ac016_reject_wrong_date_format`. One test per AC-001 – AC-016. AC-003/AC-004 use
  `"a" * 100` / `"a" * 101`. AC-004, AC-009, AC-013 and AC-015 also assert that no
  `tasks.json` was created. Exact messages: `Error: title must be 1-100 characters.`,
  `Error: priority must be one of: low, medium, high.`,
  `Error: each tag must be 1-30 characters using only letters, digits, '-' or '_'.`,
  `Error: due date must be a valid date in YYYY-MM-DD format.` Covers: FR-001 – FR-005,
  AC-001 – AC-016.
- [X] T008 [P] [US1] Write `tests/test_cli_general.py`: `test_ac047_unknown_command_usage_exit1`
  (also `todo add` with no title; assert `"usage:"` in stderr, empty stdout, code 1),
  `test_ac048_help_lists_commands` (stdout contains `add`, `list`, `update`, `delete`,
  `status`; code 0), and `test_ac048_python_m_todo_help_subprocess`, which runs
  `subprocess.run([sys.executable, "-m", "todo", "--help"], env={..., "PYTHONPATH": "src"})`
  with list args and no shell. Covers: FR-020, AC-047, AC-048.
- [X] T009 [US1] Write `tests/test_cli_list.py` (part 1): `test_ac017_empty_list` and
  `test_ac018_sort_by_priority_then_creation` (tasks A low, B high, C medium, D high → ids
  2, 4, 3, 1). Covers: FR-006, FR-007, AC-017, AC-018.
- [X] T010 [US3] Extend `tests/test_cli_list.py` (part 2): `test_ac019_filter_by_tag` …
  `test_ac024_filter_tag_and_status`. AC-022 uses titles `Write report`/`File taxes`, with
  the `done` state set via `write_store`. AC-023 checks
  `Error: status must be one of: todo, in_progress, done.` Depends on T009 (same file).
  Covers: FR-008, FR-009, AC-019 – AC-024.
- [X] T011 [US2] Extend `tests/test_cli_list.py` (part 3): `test_ac051_plain_list_shows_all_statuses`,
  asserting the exact three lines from spec AC-051. Depends on T010 (same file). Covers: FR-006,
  AC-051.
- [X] T012 [P] [US2] Write `tests/test_cli_status.py`: `test_ac033_todo_to_in_progress` …
  `test_ac039_invalid_status_value`, plus `test_ac049_edit_done_task` and
  `test_ac050_delete_done_task`. AC-038 is parametrized over `todo`, `in_progress` and `done`
  and checks `Error: task 1 is done; its status cannot be changed.` Every rejected case also
  asserts the status is unchanged in `todo list`. Covers: FR-013 – FR-015, AC-033 – AC-039,
  AC-049, AC-050.
- [X] T013 [P] [US4] Write `tests/test_cli_update_delete.py`: `test_ac025_update_title_only` …
  `test_ac032_invalid_id_format` (AC-032 parametrized over `abc`, `0`, `-1` for `delete`,
  `update`, `status`; AC-031 likewise for not-found id 99), plus
  `test_ac052_update_due_date`, `test_ac053_clear_due_date` and
  `test_ac054_reject_invalid_due_on_update`. AC-029 message:
  `Error: nothing to update; provide --title, --priority, --tags or --due.` Covers: FR-010 –
  FR-012, AC-025 – AC-032, AC-052 – AC-054.
- [X] T014 [P] [US4] Write `tests/test_cli_ids_storage.py` (part 1):
  `test_ac040_id_not_reused_after_delete_last`, `test_ac041_id_not_reused_after_delete_all`.
  Covers: FR-016, AC-040, AC-041.
- [X] T015 [US5] Extend `tests/test_cli_ids_storage.py` (part 2):
  - `test_ac042_persists_between_runs`
  - `test_ac043_list_does_not_create_file`
  - `test_ac044_corrupt_json_untouched` (parametrized over `list` and `add "X"`; compare raw
    bytes before and after)
  - `test_ac045_wrong_structure_untouched` (parametrized: `[]`, missing title, empty file,
    duplicate ids, bad status, `next_id` ≤ max id, unknown top-level key `"notes": "x"`, unknown
    task key `"notes": "x"`)
  - `test_ac055_unreadable_file_exit2`: create a valid `tasks.json`, then
    `monkeypatch.setattr(pathlib.Path, "read_bytes", raiser)` raising `PermissionError`; assert
    stderr `Error: could not read tasks.json.\n`, empty stdout, exit 2, file bytes unchanged
  - `test_ac046_save_failure_keeps_file`: `monkeypatch.setattr(os, "replace", raiser)`; assert
    `Error: could not save tasks.json; no changes were made.`, exit 2, original bytes intact,
    and no `.tasks-*.tmp` left in `tmp_path`

  Depends on T014 (same file). Covers: FR-017 – FR-019, AC-042 – AC-046, AC-055.
- [X] T016 [P] Write unit tests `tests/test_models.py` for the validators in data-model.md:
  `validate_title`, `parse_priority`, `parse_tags`, `parse_due`, `parse_status`,
  `parse_task_id`, `check_transition`. Cover the full transition table, including
  `in_progress → in_progress` rejected. Use `test_acNNN_` prefixes where a case maps to an AC
  (e.g. `test_ac012_tags_dedup_lowercase`), otherwise `test_unit_...`. Covers: FR-002 –
  FR-005, FR-012 – FR-015.
- [X] T017 [P] Write unit tests `tests/test_storage.py`: load of a missing file returns an empty
  store with `next_id = 1`; round-trip save/load keeps UTF-8 titles such as `Café ☕`; every
  validity rule 1–5 in contracts/tasks-file.md raises `CorruptStoreError`, including an extra
  unknown key at the top level and inside a task; a failed
  `os.replace` raises `SaveError` and removes the temp file; a non-ENOENT `OSError` on read
  raises `StorageError`. Covers: FR-017 – FR-019.
- [X] T018 [P] Write `tests/test_performance.py`. Seed 1,000 tasks via `write_store`, then time
  each run with `time.perf_counter()`, asserting each is < 1.0 s:
  - `test_sc002_list_and_add_with_1000_tasks_under_1s`: `list` and `add` called in-process via
    `run(...)`
  - `test_sc002_end_to_end_subprocess_under_1s`: `list` and `add` run as
    `subprocess.run([sys.executable, "-m", "todo", ...], cwd=tmp_path, env={..., "PYTHONPATH":
    <abs path to src>})` (list args, no shell), so interpreter start-up is included; also assert
    exit code 0

  Covers: SC-002.
- [X] T019 Run `python -m pytest`. Confirm every test **fails or errors** (no implementation
  yet) and none pass by accident. Record the summary line in the Phase 2 commit message.
  Covers: constitution III (red phase).

**Checkpoint**: Every AC-001 – AC-055 has at least one `test_acNNN_` test; the suite is red.
Commit.

---

## Phase 3: Harness

**Purpose**: One command that enforces every constitution gate and writes evidence.

- [X] T020 Create `.harness/run_harness.py` (stdlib only; `subprocess.run` with list args,
  `shell=False`, `sys.executable -m <tool>`, `cwd` = `Part-1A`). CLI option `--label NAME`
  (default `latest`) writes into `evidence/<label>/`. Steps, each saving combined output to
  `<step>.txt`:
  1. `ruff`: `ruff check .`
  2. `bandit`: `bandit -r src -ll` (zero Medium/High)
  3. `pytest`: `pytest --cov=src --cov-report=term-missing
     --cov-report=xml:evidence/<label>/coverage.xml --cov-fail-under=85
     --junitxml=evidence/<label>/junit.xml`

  Covers: constitution I, II, III, VI.
- [X] T021 Add a traceability step to `.harness/run_harness.py`: collect every `AC-\d{3}` in
  `specs/001-smart-todo-cli/spec.md`, and every `def test_ac(\d{3})` in `tests/*.py`. Write
  `traceability.txt` listing each AC and its test names. The step fails if any AC has no test.
  Depends on T020. Covers: constitution III; AC-001 – AC-055 traceability.
- [X] T022 Add summary output to `.harness/run_harness.py`. Write `summary.json` (timestamp,
  Python version, tool versions, per-step `{exit_code, passed}`, coverage percent parsed from
  coverage.xml, ACs traced/total, `overall`: `pass`/`fail`) and `summary.md` (table of the
  same). Print `OVERALL: PASS|FAIL` and exit 0 only if every step passed. Depends on T021.
  Covers: constitution III, VII (auditable evidence).
- [X] T023 Run `python .harness\run_harness.py --label red-baseline`. Expected result: ruff
  PASS, bandit PASS, traceability PASS (55/55), pytest FAIL (red). If ruff or traceability
  fail, fix the tests or harness (without weakening any check). Commit `evidence/red-baseline/`.
  Covers: constitution III (red phase evidence).

**Checkpoint**: Harness works; red baseline recorded. Commit.

---

## Phase 4: Implementation (`src/todo/`)

**Purpose**: Make the Phase 2 tests pass, layer by layer (`models → storage → service → cli`),
story by story. Do not edit tests except to fix a genuine bug in the test itself, and record any
such fix in the commit message.

### Foundation (blocks all stories)

- [X] T024 Implement the core types in `src/todo/models.py` per data-model.md:
  - `Status(StrEnum)`: `todo`, `in_progress`, `done`
  - `Priority(StrEnum)`: `low`, `medium`, `high`, with `PRIORITY_RANK = {high: 0, medium: 1,
    low: 2}`
  - `@dataclass Task(id: int, title: str, status: Status, priority: Priority, tags: list[str],
    due: str | None)` with `to_dict()` and `from_dict()`
  - exceptions `TodoError` → `ValidationError` → `NotFoundError`

  Covers: FR-001, FR-003, FR-007, FR-013.
- [X] T025 Implement the validators in `src/todo/models.py` with the exact contract messages:
  - `validate_title`: "1–100 characters after `strip()`", returns the stripped title
  - `parse_priority`: case-insensitive, `low|medium|high`
  - `parse_tags`: split on `,`, `strip().lower()`, drop empties, de-dup keeping order, each
    matching `^[a-z0-9_-]{1,30}$`
  - `parse_due`: regex `^\d{4}-\d{2}-\d{2}$` plus `date.fromisoformat`; `""` → `None`
  - `parse_status`: exact `todo|in_progress|done`
  - `parse_task_id`: `^\d+$` and > 0, otherwise `task id must be a positive integer.`
  - `check_transition(task_id, old, new)`: the table in data-model.md

  Depends on T024. Covers: FR-002 – FR-005, FR-009, FR-012 – FR-015.
- [X] T026 Implement loading in `src/todo/storage.py`:
  - `TaskStore(version, next_id, tasks)` dataclass
  - `StorageError` → `CorruptStoreError`, `SaveError`
  - `load(path: Path) -> TaskStore`: a missing file gives an empty store and is not created;
    otherwise read with `path.read_bytes()` → UTF-8 → `json.loads` → apply validity rules 1–5 of
    contracts/tasks-file.md, where **exactly** the listed keys are allowed (any extra key at top
    level or in a task is corrupt)
  - message texts: corrupt `tasks.json is corrupt and was not modified. Fix or remove it and try
    again.`; any other `OSError` while reading `could not read tasks.json.`

  Depends on T024, T025. Covers: FR-017, FR-018, AC-043 – AC-045, AC-055.
- [X] T027 Implement `save(path, store)` in `src/todo/storage.py` per research.md R1:
  `tempfile.mkstemp(dir=path.parent, prefix=".tasks-", suffix=".tmp")`, write
  `json.dumps(..., ensure_ascii=False, indent=2) + "\n"` as UTF-8, `flush` + `os.fsync`, then
  `os.replace`. On any exception, unlink the temp file and raise
  `SaveError("could not save tasks.json; no changes were made.")`. Depends on T026.
  Covers: FR-016, FR-019, AC-046, constitution V.
- [X] T028 Implement the CLI skeleton in `src/todo/cli.py` and `src/todo/__main__.py`:
  - `_Parser(argparse.ArgumentParser)` with `error()` → usage to stderr, exit 1
  - subparsers `add`, `list`, `update`, `delete`, `status` per contracts/cli.md grammar, taking
    ids, priority and status as plain `str`
  - `main(argv=None) -> int`: reconfigure stdout/stderr to UTF-8 (`errors="replace"`), run the
    handler, map `ValidationError` → print `Error: <msg>`, return 1, and `StorageError` →
    print `Error: <msg>`, return 2
  - `__main__.py`: `raise SystemExit(main())`

  Depends on T024. Covers: FR-020, AC-047, AC-048, constitution VIII.

### User Story 1 – Capture and see tasks (P1, MVP)

- [X] T029 [US1] Implement `TodoService(path)` in `src/todo/service.py`:
  - `add(title, priority=None, tags=None, due=None) -> Task`: load first, validate, assign
    `next_id`, increment it, save
  - `list_tasks(tag=None, status=None) -> list[Task]`: sorted by `(PRIORITY_RANK, id)`; never
    saves

  Depends on T025, T027. Covers: FR-001 – FR-007, FR-016, AC-001 – AC-018.
- [X] T030 [US1] Implement the `add` and `list` handlers in `src/todo/cli.py`:
  - `add` prints `Added task <id>: <title>`
  - `list` formats lines as `<id> | <status> | <priority> | <title> | tags: <t1,t2 or -> |
    due: <date or ->`, or prints `No tasks found.`

  Run `python -m pytest tests/test_cli_add.py tests/test_cli_general.py
  tests/test_cli_list.py -k "ac017 or ac018 or not test_cli_list"` until the US1 tests pass. Depends on T028, T029.
  Covers: FR-001 – FR-007, FR-020, AC-001 – AC-018, AC-047, AC-048.

**Checkpoint (MVP)**: AC-001 – AC-018, AC-047 and AC-048 pass.

### User Story 2 – Track progress through statuses (P2)

- [X] T031 [US2] Add `set_status(task_id, new_status) -> tuple[Status, Status]` to
  `src/todo/service.py`. Order: load → `parse_task_id` → `parse_status` → look up (else
  `NotFoundError("task <id> not found.")`) → `check_transition` → save. Depends on T029.
  Covers: FR-012 – FR-015, AC-033 – AC-039.
- [X] T032 [US2] Add the `status` handler to `src/todo/cli.py`, printing
  `Task <id> status: <old> -> <new>`. Make `tests/test_cli_status.py` (except AC-049/AC-050,
  which need US4) and `test_ac051` pass. Depends on T030, T031. Covers: FR-006, FR-013 –
  FR-015, AC-033 – AC-039, AC-051.

### User Story 3 – Filter the list (P3)

- [X] T033 [US3] Implement filtering in `TodoService.list_tasks` in `src/todo/service.py`
  (`tag`: `strip().lower()` membership; `status`: `parse_status`; AND-combined, applied before
  sorting). Wire `--tag`/`--status` in the `list` handler in `src/todo/cli.py`. Make AC-019 –
  AC-024 pass. Depends on T030. Covers: FR-008, FR-009, AC-019 – AC-024.

### User Story 4 – Edit and remove tasks (P3)

- [X] T034 [US4] Add `update(task_id, title=None, priority=None, tags=None, due=None)` and
  `delete(task_id)` to `src/todo/service.py`:
  - `None` means "not given"; `""` for tags/due clears the field
  - if no field is given: `ValidationError("nothing to update; provide --title, --priority,
    --tags or --due.")`
  - allowed in every status, including `done`
  - `delete` never changes `next_id`

  Order: load → id format → field validation → look up → save. Depends on T029.
  Covers: FR-010 – FR-012, FR-015, FR-016.
- [X] T035 [US4] Add the `update` and `delete` handlers to `src/todo/cli.py`, printing
  `Updated task <id>.` / `Deleted task <id>.` Make `tests/test_cli_update_delete.py`, AC-040,
  AC-041, AC-049 and AC-050 pass. Depends on T032, T034. Covers: FR-010 – FR-012, FR-015,
  FR-016, AC-025 – AC-032, AC-040, AC-041, AC-049, AC-050, AC-052 – AC-054.

### User Story 5 – Data is safe (P2)

- [X] T036 [US5] Verify the storage behaviour end-to-end through the CLI. Make
  `tests/test_cli_ids_storage.py` AC-042 – AC-046, AC-055 and `tests/test_storage.py` pass, fixing
  `src/todo/storage.py` or `src/todo/service.py` as needed, never the tests. Confirm that a
  corrupt file wins over invalid arguments (load happens first). Depends on T027, T035.
  Covers: FR-017 – FR-019, AC-042 – AC-046, AC-055, SC-003.

### Cross-cutting

- [X] T037 Make `tests/test_models.py`, `tests/test_service.py` (if present) and
  `tests/test_performance.py` pass; profile only if SC-002 fails. Run `python -m pytest` and
  confirm the full suite is green. Depends on T036. Covers: SC-002; FR-002 – FR-005,
  FR-012 – FR-015.

**Checkpoint**: Full suite green locally. Commit.

---

## Phase 5: Final Harness Run & Evidence

- [ ] T038 Run `python .harness\run_harness.py --label final`. Fix any failures in
  `src/` until it prints `OVERALL: PASS` (ruff 0 errors, bandit 0 Medium/High, all tests pass,
  coverage ≥ 85 %, 55/55 ACs traced). Do not change the gates (constitution VII). Covers:
  constitution I – III, SC-001.
- [ ] T039 [P] Walk through the quickstart.md §2 smoke scenario manually in a temp folder and
  confirm each printed line and `$LASTEXITCODE` matches. (Quickstart §3 already points at
  `evidence\<label>\`, fixed for finding I2.) Covers: SC-004, FR-020.
- [ ] T040 Commit and push `evidence/final/` together with the code. The commit message must
  quote the coverage percent and `55/55 ACs traced`. Covers: constitution III, VII (evidence
  preserved).

---

## Dependencies & Execution Order

### Phase dependencies

1. **Setup (T001 – T005)**: none. T004 needs T001 and T002.
2. **Tests (T006 – T019)**: need Setup. T006 comes first; then the [P] test files can be written
   in parallel; tasks sharing a file are sequential (T009 → T010 → T011; T014 → T015). T019
   comes last.
3. **Harness (T020 – T023)**: needs the Tests phase (traceability reads the tests).
   Sequential: same file.
4. **Implementation (T024 – T037)**: needs the Harness phase (red baseline recorded).
   Foundation T024 → T025 → T026 → T027, with T028 after T024. Then US1 (T029 – T030) → US2
   (T031 – T032) → US3 (T033) → US4 (T034 – T035) → US5 (T036) → T037.
5. **Final (T038 – T040)**: needs the full suite green.

### User story dependencies

- **US1** is the base: it introduces `TodoService`, `add` and `list`.
- **US2**, **US3** and **US4** depend only on US1. They are serialized because they edit the
  same files (`service.py`, `cli.py`).
- **US2's** AC-049/AC-050 (editing or deleting a done task) need US4's `update` and `delete`.
  They are verified in T035.
- **US5** relies on the storage foundation (T026, T027) and on commands from US1 and US4.

### Parallel opportunities

- Phase 1: T002, T003 and T005 alongside T001.
- Phase 2: after T006, write T007, T008, T009, T012, T013, T014, T016, T017 and T018 in parallel
  (all different files).
- Phase 4: T028 (cli skeleton) can run in parallel with T025 – T027 (models and storage).
- Phase 5: T039 alongside T038's fix loop.

## Parallel Example: Phase 2 tests

```text
Task: "T007 [US1] tests/test_cli_add.py – AC-001..AC-016"
Task: "T008 [US1] tests/test_cli_general.py – AC-047, AC-048"
Task: "T012 [US2] tests/test_cli_status.py – AC-033..AC-039, AC-049, AC-050"
Task: "T013 [US4] tests/test_cli_update_delete.py – AC-025..AC-032, AC-052..AC-054"
Task: "T014 [US4] tests/test_cli_ids_storage.py – AC-040, AC-041"
Task: "T016 tests/test_models.py, T017 tests/test_storage.py, T018 tests/test_performance.py"
```

---

## Implementation Strategy

### MVP first

Complete Phases 1 – 3, then Foundation (T024 – T028) and US1 (T029 – T030). Stop and check
that AC-001 – AC-018, AC-047 and AC-048 pass. The user can then add and list tasks.

### Incremental delivery

US1 → US2 (statuses) → US3 (filters) → US4 (edit/delete) → US5 (safety verification). After each
story, run `python -m pytest`. Earlier stories' tests must stay green.

## Notes

- `test_service.py` from plan.md is optional. The CLI tests plus `test_models.py` and
  `test_storage.py` are expected to reach ≥ 85 % coverage. Add `tests/test_service.py` only if
  T038 shows a coverage gap in `service.py`.
- Commit after each phase checkpoint (CLAUDE.md).
