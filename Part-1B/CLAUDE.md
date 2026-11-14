# CLAUDE.md

Project rules for Claude Code in Part 1B (Expense Claim Assistant). The project constitution at
`.specify/memory/constitution.md` also applies and takes precedence on any conflict.

## Git

- Commit and push on the current branch.
- Do not create extra branches yourself. Branches created by Spec Kit commands
  (e.g. `/speckit-specify`) are fine.

## Constitution change history

- Keep the Sync Impact Report (change-summary history) at the top of
  `.specify/memory/constitution.md`; do not delete it before committing.
- On every amendment, add a new dated entry to that history (version change, modified/added/
  removed principles or sections, follow-up TODOs) and keep all earlier entries.

## Secrets

- Never open, read, print, cat, grep or otherwise access the contents of the `.env` file.
- Refer to the API key only via the `GEMINI_API_KEY` environment variable name.
