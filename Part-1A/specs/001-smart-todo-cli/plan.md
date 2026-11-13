# Implementation Plan: Smart Todo CLI

**Branch**: `main` (Spec Kit feature id `001-smart-todo-cli`; no git branch per CLAUDE.md) | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-smart-todo-cli/spec.md`

## Summary

A single-user terminal todo manager: add, list (filter + priority sort), update, delete and
change the status of tasks, persisted in one `tasks.json` file in the current directory. It is
built as a pure-standard-library Python 3.12 package `src/todo/` with four layers (models →
storage → service → cli) and an `argparse` front end runnable as `python -m todo` or via a
`todo` console script. Every acceptance criterion (AC-001 – AC-055) maps to a named pytest test.
A harness in `.harness/run_harness.py` runs Ruff, Bandit and pytest with coverage and writes
results to `evidence/`.

## Technical Context

**Language/Version**: Python 3.12 (verified in `.venv`: 3.12.10)

**Primary Dependencies**: None at runtime (standard library only: `argparse`, `json`,
`dataclasses`, `enum`, `datetime`, `os`, `pathlib`, `tempfile`, `re`, `sys`). Dev only: `ruff`,
`bandit`, `pytest`, `pytest-cov`.

**Storage**: Single JSON file `tasks.json` in the current working directory, written atomically
(temp file in same directory → `os.replace`). Schema in
[contracts/tasks-file.md](contracts/tasks-file.md).

**Testing**: pytest + pytest-cov; `pyproject.toml` sets `pythonpath = ["src"]`. Coverage gate
`--cov-fail-under=85`.

**Target Platform**: Windows 11, PowerShell 5.1+, virtual environment `.venv`.

**Project Type**: CLI tool (single project).

**Performance Goals**: Each command < 1 s with 1,000 stored tasks (SC-002).

**Constraints**: Standard library only at runtime; no network, no `eval`/`exec`, no
`shell=True`; exit codes 0/1/2; corrupt file never modified.

**Scale/Scope**: One user, up to ~1,000s of tasks, 5 commands, ~54 acceptance tests.

No NEEDS CLARIFICATION items remain; design decisions are recorded in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies | Pre | Post |
|---|-----------|------------------------|-----|------|
| I | Ruff zero errors | Ruff config in `pyproject.toml`; harness runs `ruff check .` over `src/`, `tests/`, `.harness/` | ✅ | ✅ |
| II | Bandit zero Medium/High | Harness runs `bandit -r src -ll`; design uses no risky APIs (see VI) | ✅ | ✅ |
| III | Every AC tested, ≥ 85 % coverage | One or more tests per AC named `test_acNNN_*` (traceability matrix in quickstart); `--cov-fail-under=85` | ✅ | ✅ |
| IV | Stdlib-only runtime (v1.1.0) | `[project] dependencies = []`; dev tools only in `[project.optional-dependencies] dev`; setuptools only in `[build-system]`; installs via `uv pip install --system-certs` | ✅ | ✅ |
| V | One JSON file, atomic writes | `storage.py` writes `tasks.json` via `tempfile.mkstemp` in the same dir, `fsync`, `os.replace`; temp removed on failure | ✅ | ✅ |
| VI | No secrets/network/eval/exec/`shell=True` | None used in `src/`. The harness uses `subprocess.run([...])` with list args and `shell=False` | ✅ | ✅ |
| VII | Spec integrity / harness protection | Tests and harness config are never weakened; spec changes only via `spec.md` Change Log | ✅ | ✅ |
| VIII | Exit codes 0/1/2 | `argparse` error exit overridden from 2 → 1; domain errors map to 1, storage errors to 2 (see [contracts/cli.md](contracts/cli.md)) | ✅ | ✅ |
| IX | Windows/PowerShell, `.venv` | All commands documented in PowerShell; `pathlib` everywhere; `os.replace` (overwrites on Windows) | ✅ | ✅ |

**Result**: PASS (no violations; Complexity Tracking not needed).

Note on Principle VIII: `argparse` exits with code 2 on usage errors by default, which would
collide with "storage error". The CLI uses an `ArgumentParser` subclass whose `error()` prints
usage to stderr and exits 1 (AC-047).

## Project Structure

### Documentation (this feature)

```text
specs/001-smart-todo-cli/
├── plan.md              # This file
├── research.md          # Phase 0: design decisions
├── data-model.md        # Phase 1: Task / TaskStore entities, validation, state machine
├── quickstart.md        # Phase 1: setup, run, validation guide, AC → test matrix
├── contracts/
│   ├── cli.md           # Command grammar, output formats, messages, exit codes
│   └── tasks-file.md    # tasks.json schema and corruption rules
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (Part-1A project root)

```text
pyproject.toml            # project metadata, console script, pytest + Ruff config
src/
└── todo/
    ├── __init__.py
    ├── __main__.py       # `python -m todo` → sys.exit(cli.main())
    ├── models.py         # Status/Priority enums, Task dataclass, validators, domain errors
    ├── storage.py        # load/save tasks.json, schema validation, atomic write, StorageError
    ├── service.py        # TodoService: add, list, update, delete, set_status, id allocation
    └── cli.py            # argparse parser, formatting, error → exit code mapping, main(argv)

tests/
├── conftest.py           # tmp working dir fixture, run_cli helper (in-process main + capsys)
├── test_models.py        # validators, transitions (unit)
├── test_storage.py       # load/save, corruption, atomic write failure (unit)
├── test_service.py       # business rules (unit; optional, add only if coverage needs it)
├── test_cli_add.py       # AC-001 – AC-016
├── test_cli_list.py      # AC-017 – AC-024, AC-051
├── test_cli_update_delete.py  # AC-025 – AC-032, AC-052 – AC-054
├── test_cli_status.py    # AC-033 – AC-039, AC-049, AC-050
├── test_cli_ids_storage.py    # AC-040 – AC-046, AC-055
├── test_cli_general.py   # AC-047, AC-048, `python -m todo` smoke test
└── test_performance.py   # SC-002: 1,000 tasks < 1 s (in-process and end-to-end subprocess)

.harness/
└── run_harness.py        # runs ruff, bandit, pytest+coverage; writes evidence/

evidence/                 # harness output (committed as assignment evidence)
```

**Structure Decision**: Single-project `src/` layout with one package `todo` split into the four
modules the user requested. Dependencies point one way only:
`cli → service → storage → models`. `cli.py` is the only module that prints or chooses exit
codes; lower layers raise typed exceptions. Tests call `cli.main(argv)` in-process for speed and
coverage, plus one subprocess smoke test of `python -m todo`.

## Complexity Tracking

No constitution violations; nothing to justify.
