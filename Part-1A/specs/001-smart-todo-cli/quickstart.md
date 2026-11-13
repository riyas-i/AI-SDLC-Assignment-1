# Quickstart & Validation Guide: Smart Todo CLI

All commands are PowerShell and run from the `Part-1A` folder.

## 1. Set up

```powershell
.\.venv\Scripts\Activate.ps1          # Python 3.12 virtual environment
python --version                      # expect: Python 3.12.x
python -m pip install -e ".[dev]"     # installs ruff, bandit, pytest, pytest-cov + `todo` command
```

## 2. Try it (end-to-end smoke scenario)

Run in a scratch folder so the project's own directory gets no `tasks.json`:

```powershell
$work = New-Item -ItemType Directory -Force "$env:TEMP\todo-demo"; Push-Location $work
todo add "Pay rent" --priority high --tags "home,bills" --due 2026-12-01   # Added task 1: Pay rent
todo add "Buy milk"                                                        # Added task 2: Buy milk
todo list
#   1 | todo | high | Pay rent | tags: home,bills | due: 2026-12-01
#   2 | todo | medium | Buy milk | tags: - | due: -
todo status 1 in_progress        # Task 1 status: todo -> in_progress
todo status 1 done               # Task 1 status: in_progress -> done
todo status 1 todo; $LASTEXITCODE   # Error: task 1 is done; its status cannot be changed.  -> 1
Set-Content tasks.json "{not json"
todo list; $LASTEXITCODE            # Error: tasks.json is corrupt and was not modified. ...  -> 2
Pop-Location
```

`python -m todo ...` is equivalent to `todo ...`. A title that starts with `-` needs `--`, for
example `todo add -- "-weird title"`.

Exact command grammar, output formats and every error message:
[contracts/cli.md](contracts/cli.md). File format: [contracts/tasks-file.md](contracts/tasks-file.md).

## 3. Run the quality gates

```powershell
python .harness\run_harness.py      # exit 0 only if every gate passes
Get-Content evidence\summary.md
```

| Gate | Command run by the harness | Pass condition |
|------|----------------------------|----------------|
| Lint | `ruff check .` | 0 errors |
| Security | `bandit -r src -ll` | 0 Medium/High issues |
| Tests + coverage | `pytest --cov=src --cov-fail-under=85 ...` | all pass, ≥ 85 % lines |
| Traceability | every `AC-NNN` in `spec.md` has a `test_acNNN_*` test | no missing ACs |

Evidence files written to `evidence/`: `ruff.txt`, `bandit.txt`, `pytest.txt`, `junit.xml`,
`coverage.xml`, `traceability.txt`, `summary.json`, `summary.md`.

## 4. Acceptance criteria → test file map

| ACs | Requirement(s) | Test file |
|-----|----------------|-----------|
| AC-001 – AC-016 | FR-001 – FR-005 (add + validation) | `tests/test_cli_add.py` |
| AC-017 – AC-024, AC-051 | FR-006 – FR-009 (list, sort, filters) | `tests/test_cli_list.py` |
| AC-025 – AC-032, AC-052 – AC-054 | FR-010 – FR-012 (update, delete, ids) | `tests/test_cli_update_delete.py` |
| AC-033 – AC-039, AC-049, AC-050 | FR-013 – FR-015 (status, done tasks) | `tests/test_cli_status.py` |
| AC-040 – AC-046 | FR-016 – FR-019 (ids, persistence, corruption, save failure) | `tests/test_cli_ids_storage.py` |
| AC-047, AC-048 | FR-020 (usage, help) | `tests/test_cli_general.py` |
| SC-002 | performance (1,000 tasks < 1 s) | `tests/test_performance.py` |

Test functions are named `test_acNNN_<short_description>`, so this works:
`Select-String -Path tests\*.py -Pattern "def test_ac044"`.

## 5. Expected outcome

- `python .harness\run_harness.py` prints `OVERALL: PASS` and exits 0.
- `evidence\summary.json` shows `"overall": "pass"`, with coverage ≥ 85 % and 54/54 ACs traced.
