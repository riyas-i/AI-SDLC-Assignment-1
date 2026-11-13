<!--
Sync Impact Report
==================
Entries are kept as change history (newest first); see CLAUDE.md.

--- Amendment 2026-11-13 ---
Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR. Materially expanded guidance in Principle IV: names the permitted build
backend (setuptools, build-time only) and package installer (uv). No principle removed or
redefined.

Modified principles:
  - IV. Standard-Library-Only Runtime (title unchanged; added "Build and install tooling" rules)

Modified sections:
  - Technology & Platform Constraints (added build backend and installer lines)

Added sections: none
Removed sections: none

Trigger: /speckit-analyze finding C1. The plan's `[build-system]` uses setuptools for
`uv pip install -e .`, which v1.0.0 would have required an amendment to allow.

Follow-up TODOs: none.

--- Ratification 2026-11-13 ---
Version change: (unversioned template) → 1.0.0
Bump rationale: Initial ratification; all placeholders replaced with concrete governance.

Modified principles (template slot → new title):
  - [PRINCIPLE_1_NAME] → I. Lint-Clean Code (Ruff)
  - [PRINCIPLE_2_NAME] → II. Static Security Gate (Bandit)
  - [PRINCIPLE_3_NAME] → III. Acceptance-Criteria Test Coverage (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Standard-Library-Only Runtime
  - [PRINCIPLE_5_NAME] → V. Single JSON Store with Atomic Writes
  - (added) VI. Secure-by-Construction Code
  - (added) VII. Spec Integrity and Harness Protection (NON-NEGOTIABLE)
  - (added) VIII. Deterministic CLI Exit Codes
  - (added) IX. Windows / PowerShell Platform Baseline

Added sections:
  - Technology & Platform Constraints (was [SECTION_2_NAME])
  - Development Workflow & Quality Gates (was [SECTION_3_NAME])

Removed sections: none

Follow-up TODOs: none. Ratification date set to first adoption date (2026-11-13).
-->

# Smart Todo CLI Constitution

## Core Principles

### I. Lint-Clean Code (Ruff)

All Python source and test code MUST pass `ruff check` with zero errors. Ruff configuration
lives in `pyproject.toml` and MUST NOT be loosened (e.g., removing rule sets, adding broad
ignores, or blanket `# noqa`) to make code pass. A targeted `# noqa: <CODE>` is permitted only
with an inline justification comment.

**Rationale**: A zero-error lint baseline keeps the codebase consistent and catches defects
early at negligible cost.

### II. Static Security Gate (Bandit)

`bandit -r` over the source package MUST report zero issues of Medium or High severity.
Low-severity findings MUST be reviewed; any `# nosec` suppression MUST name the specific test
ID and carry a justification.

**Rationale**: Automated static security analysis provides an objective, repeatable security
bar for every change.

### III. Acceptance-Criteria Test Coverage (NON-NEGOTIABLE)

- Every acceptance criterion in `spec.md` MUST be verified by at least one pytest test, and
  the test MUST reference the criterion it covers (e.g., by ID in the test name or docstring).
- Line coverage measured by `pytest-cov` MUST be at least 85% for the source package; the
  threshold MUST be enforced via `--cov-fail-under=85`.
- The full test suite MUST pass before any change is considered complete.

**Rationale**: Traceability from criterion to test proves the spec is implemented; a coverage
floor guards against untested code paths.

### IV. Standard-Library-Only Runtime

The application at runtime MUST depend only on the Python 3.12 standard library. Third-party
packages are permitted solely as development tools: `ruff`, `bandit`, `pytest`, `pytest-cov`.
Adding any other dependency — runtime or dev — requires a constitution amendment.

**Build and install tooling** (permitted; never imported by application code):
- `setuptools` MAY be used as the build backend, declared only in `pyproject.toml`
  `[build-system]`. It is a build-time dependency, not a runtime one.
- `uv` is the package installer. Packages MUST be installed into `.venv` with
  `uv pip install --system-certs ...`; plain `pip` MUST NOT be used (the development network
  blocks it).

**Rationale**: Zero runtime dependencies eliminate supply-chain risk and make installation
trivial. A build backend and an installer are needed for an editable install and the `todo`
command, but neither ships with or runs inside the application.

### V. Single JSON Store with Atomic Writes

- All persistent data MUST be stored in exactly one JSON file.
- Every write MUST be atomic: serialize to a temporary file in the same directory, flush and
  close it, then replace the target with `os.replace()`.
- A failed or interrupted write MUST leave the previous data file intact and readable.

**Rationale**: One file keeps storage simple and inspectable; atomic replace prevents
corruption on crash or power loss.

### VI. Secure-by-Construction Code

The codebase MUST NOT contain:
- Secrets, credentials, API keys, or tokens of any kind.
- Network calls (no `socket`, `urllib.request`, `http.client`, or equivalent usage).
- `eval`, `exec`, or dynamic code compilation of untrusted input.
- `subprocess` (or `os.system`/`os.popen`) invocations with `shell=True` or shell strings.

**Rationale**: A local todo tool has no need for these capabilities; forbidding them removes
whole classes of vulnerabilities.

### VII. Spec Integrity and Harness Protection (NON-NEGOTIABLE)

The coding agent (human or AI) MUST NOT:
- Weaken, remove, or reinterpret acceptance criteria to make an implementation pass.
- Delete, skip (`@pytest.mark.skip`, `xfail`, `pytest.skip`), or neuter failing tests.
- Disable, bypass, or relax harness checks (Ruff, Bandit, pytest, coverage threshold, or
  their configuration).

Any change to requirements MUST be made in `spec.md` and accompanied by a dated change note
(`YYYY-MM-DD: <what changed and why>`) in that file's change log.

**Rationale**: The spec and harness are the source of truth; letting the implementer edit them
silently would make every quality gate meaningless.

### VIII. Deterministic CLI Exit Codes

The CLI MUST exit with:
- `0` — success.
- `1` — user or validation error (bad arguments, invalid input, unknown task ID).
- `2` — storage error (data file unreadable, corrupt JSON, write failure).

Error messages MUST go to stderr; normal output goes to stdout. Each exit code path MUST be
covered by at least one test.

**Rationale**: Stable exit codes make the tool scriptable and its failure modes testable.

### IX. Windows / PowerShell Platform Baseline

The project MUST run on Windows with PowerShell as the reference environment. The virtual
environment MUST be `.venv` at the repository root. All documented commands MUST be valid
PowerShell (e.g., `.\.venv\Scripts\Activate.ps1`). File paths MUST be handled with `pathlib`
and MUST NOT assume POSIX separators.

**Rationale**: A single, explicit reference platform removes "works on my machine" ambiguity.

## Technology & Platform Constraints

- Language: Python 3.12.
- Runtime dependencies: Python standard library only (Principle IV).
- Dev tools: `ruff`, `bandit`, `pytest`, `pytest-cov`, installed into `.venv`.
- Build backend: `setuptools` (build-time only, `[build-system]`).
- Installer: `uv pip install --system-certs ...` (never plain `pip`).
- Storage: a single JSON file written atomically (Principle V).
- Interface: command-line only, with exit codes per Principle VIII.
- Platform: Windows + PowerShell (Principle IX).

## Development Workflow & Quality Gates

Before any change is considered done, all of the following MUST pass from the `.venv`:

```powershell
ruff check .
bandit -r src -ll            # -ll: report Medium and above; must be zero
pytest --cov=src --cov-fail-under=85
```

- Spec Kit flow: `spec.md` → `plan.md` → `tasks.md` → implementation; each plan MUST include a
  Constitution Check against Principles I–IX.
- Any gate failure MUST be fixed in the code, never by altering the gate (Principle VII).

## Governance

- This constitution supersedes all other project practices and guidance. Where a plan, task,
  or agent instruction conflicts with it, the constitution wins.
- Amendments MUST be made by editing this file, with a Sync Impact Report, a version bump, and
  an updated Last Amended date.
- Versioning follows semantic versioning:
  - MAJOR: removal or backward-incompatible redefinition of a principle.
  - MINOR: new principle or section, or materially expanded guidance.
  - PATCH: clarifications and wording fixes with no semantic change.
- Compliance review: every plan's Constitution Check and every change review MUST verify
  adherence to Principles I–IX; any justified deviation MUST be recorded in the plan's
  Complexity Tracking table.

**Version**: 1.1.0 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-13
