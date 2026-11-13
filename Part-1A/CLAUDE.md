# CLAUDE.md

## Git workflow

This is a solo student assignment.

- Commit and push on the current branch. Do not create extra branches yourself.
  Branches created by Spec Kit commands (e.g., `/speckit-specify`) are fine.
- Keep the Sync Impact Report (change-summary HTML comment) at the top of
  `.specify/memory/constitution.md` when committing. The assignment requires preserving change
  history, so do not strip it; add to it on future amendments.

## Python packages

- Install Python packages only with `uv pip install --system-certs ...` inside `.venv`
  (e.g. `uv pip install --system-certs -e ".[dev]"`). Never use plain `pip`; this network
  blocks it.
