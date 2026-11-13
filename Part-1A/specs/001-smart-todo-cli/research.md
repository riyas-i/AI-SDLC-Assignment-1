# Research & Design Decisions: Smart Todo CLI

All Technical Context items were known from the user's input and the constitution. This file
records the design decisions behind them.

## R1. Atomic write on Windows

- **Decision**: `tempfile.mkstemp(dir=<tasks.json parent>, prefix=".tasks-", suffix=".tmp")` →
  write UTF-8 JSON → `flush()` + `os.fsync()` → close → `os.replace(tmp, tasks.json)`. On any
  exception, delete the temp file (ignore errors) and raise `StorageError` (save failure).
- **Rationale**: `os.replace` is atomic on the same volume and, unlike `os.rename`, overwrites an
  existing target on Windows. Keeping the temp file in the same directory guarantees same
  volume. `fsync` ensures the data is on disk before the swap.
- **Alternatives**: Write in place (corrupts on crash; violates Principle V). `os.rename`
  (fails on Windows if target exists). Backup-then-write (more files, not needed).

## R2. Detecting a corrupt `tasks.json`

- **Decision**: Read bytes → decode UTF-8 → `json.loads` → validate structure strictly against
  [contracts/tasks-file.md](contracts/tasks-file.md). Any `UnicodeDecodeError`,
  `json.JSONDecodeError` or schema violation raises `CorruptStoreError`. The file is never
  written in that case, because the command aborts before reaching save.
- **Rationale**: An empty file, invalid JSON, `[]`, or a task missing its title must all be
  "corrupt" (FR-018, AC-044, AC-045). Validating every field (types, enum values, title length,
  tag format, real dates, unique ids, `next_id > max id`) means later code can trust the data.
- **Read failure** (`OSError` other than file-not-found, e.g. permission denied): raise
  `StorageError` with `Error: could not read tasks.json.` and exit 2. This message is not in the
  spec. It falls under the constitution's "storage error = 2" rule.
- **Alternatives**: Lenient loading with defaults (could silently drop data, then overwrite it).

## R3. Never reusing ids

- **Decision**: Store `next_id` in the file. New tasks get `next_id`, which then increments.
  Deleting never decrements it. A missing file starts at `next_id = 1`.
- **Rationale**: `max(id) + 1` would reuse the id after deleting the highest task (AC-040,
  AC-041).

## R4. argparse and exit codes

- **Decision**: Subclass `argparse.ArgumentParser`, override `error()` to print usage plus
  `<prog>: error: <message>` to stderr and `sys.exit(1)`. `--help` keeps argparse's default
  (stdout, exit 0). Subcommands use `add_subparsers(dest="command", required=True)`.
- **Ids, priority and status are parsed as strings**, not with `type=int` or `choices=`, so the
  service layer produces the spec's exact messages (`Error: task id must be a positive
  integer.`, `Error: priority must be one of: ...`). argparse's own wording is used only for
  structural usage errors (AC-047).
- **Negative ids**: argparse accepts `-1` as a positional, because the parser defines no
  options that look like negative numbers. It is then rejected with the id message (AC-032).
- **Titles starting with `-`**: use `todo add -- "-x"` (standard argparse behaviour; documented
  in quickstart).
- **Rationale**: argparse's default exit code 2 would clash with the constitution's storage error
  code (Principle VIII).

## R5. Layering and error model

- **Decision**:
  - `models.py`: `Status` and `Priority` (`enum.StrEnum`), `Task` dataclass, pure validators
    (`validate_title`, `parse_priority`, `parse_tags`, `parse_due`, `parse_status`,
    `parse_task_id`, `check_transition`), and `TodoError` → `ValidationError` (exit 1).
  - `storage.py`: `load(path) -> TaskStore`, `save(path, store)`, `StorageError` →
    `CorruptStoreError`, `SaveError` (exit 2).
  - `service.py`: `TodoService(path)` with `add`, `list_tasks`, `update`, `delete`,
    `set_status`; loads, mutates, saves; raises `ValidationError` / `NotFoundError` (a subclass
    of `ValidationError`).
  - `cli.py`: builds the parser, calls the service, formats output, maps `ValidationError` → 1
    and `StorageError` → 2, prints `Error: <msg>` to stderr. `main(argv=None) -> int`.
- **Rationale**: Only `cli.py` does I/O to the terminal, so the other layers can be unit-tested
  without capturing output. Each exception class maps to exactly one exit code.
- **Validation order**: The store is loaded first, so a corrupt file always yields exit 2
  regardless of the arguments (AC-044). Then arguments are validated, then the id is looked up.
  Nothing is saved unless every check passes.

## R6. Text encoding

- **Decision**: `tasks.json` is read and written as UTF-8 with `ensure_ascii=False`,
  `indent=2`. In `main()`, call `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
  (same for stderr) when supported, so non-ASCII titles cannot crash output when it is
  redirected on Windows (cp1252 default).
- **Title length** is `len(title)` after `strip()`, which counts Unicode code points. Complex
  emoji sequences count as several characters. This is acceptable and documented.

## R7. Testing approach

- **Decision**:
  - A `cli_env` fixture `monkeypatch.chdir(tmp_path)` gives each test an isolated
    `tasks.json`.
  - A `run(*args)` helper calls `cli.main(list(args))` and returns
    `(exit_code, stdout, stderr)` via `capsys`.
  - Test names start with the AC id (`test_ac044_corrupt_file_untouched_on_list`), and the
    docstring quotes the Given/When/Then. One AC may have several tests.
  - AC-046 (save failure) uses `monkeypatch` on `os.replace` to raise `OSError`, then asserts
    the original bytes are unchanged and no `.tasks-*.tmp` file is left.
  - One subprocess smoke test runs `[sys.executable, "-m", "todo", "--help"]` with
    `env PYTHONPATH=src` (list args, no shell).
  - `test_performance.py` builds 1,000 tasks directly in the file and times `list` and `add`
    (< 1 s each).
- **Rationale**: In-process calls are fast and count toward coverage. AC-prefixed names make
  the constitution's traceability rule (Principle III) checkable with `grep`.

## R8. Harness design

- **Decision**: `.harness/run_harness.py` (stdlib only). It runs, using `sys.executable -m <tool>`
  with list arguments:
  1. `ruff check .`
  2. `bandit -r src -ll -f txt` (Medium and High severity only; must be zero)
  3. `pytest --cov=src --cov-report=term-missing --cov-report=xml:evidence/coverage.xml
     --cov-fail-under=85 --junitxml=evidence/junit.xml`
  4. An AC traceability check: every `AC-\d{3}` found in `spec.md` must appear (as `acNNN`) in
     at least one test function name under `tests/`.

  Each step's stdout and stderr go to `evidence/<step>.txt`. A run summary goes to
  `evidence/summary.json` (timestamp, Python version, per-step exit code and pass/fail, overall
  result) and `evidence/summary.md` (human-readable). The harness exits 0 only if every step
  passes.
- **Rationale**: One command reproduces all constitution gates and leaves auditable evidence.
  The traceability step enforces Principle III automatically.
- **Alternatives**: Separate PowerShell script (less portable, harder to test). `tox`/`nox`
  (extra dependencies).

## R9. Packaging and Ruff configuration

- **Decision**: `pyproject.toml` with:
  - `[project]` `name = "smart-todo"`, `requires-python = ">=3.12"`, `dependencies = []`,
    `[project.optional-dependencies] dev = ["ruff", "bandit", "pytest", "pytest-cov"]`, and
    `[project.scripts] todo = "todo.cli:main"`.
  - `[build-system]` setuptools (build-time only), `[tool.setuptools.packages.find] where = ["src"]`.
  - `[tool.pytest.ini_options]` `pythonpath = ["src"]`, `testpaths = ["tests"]`.
  - `[tool.ruff]` `target-version = "py312"`, `line-length = 100`;
    `[tool.ruff.lint] select = ["E", "F", "W", "I", "B", "UP", "SIM"]`.
- `pip install -e ".[dev]"` installs the dev tools and the `todo` command, so the spec's
  `todo ...` syntax works. `python -m todo` also works after the editable install, or with
  `$env:PYTHONPATH = "src"`.
- **Rationale**: Keeps one config file. Editable install makes the spec's command name real.
