# Implementation Plan: Expense Claim Assistant

**Branch**: `main` (no feature branch; per CLAUDE.md) | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-expense-claim-assistant/spec.md`

## Summary

A Python 3.12 CLI, `expense "<text>" --today YYYY-MM-DD`, masks card numbers and runs
deterministic injection and prohibited-item checks first. It then asks `gemini-2.5-flash`
(JSON mode, temperature 0.0) only to *extract* facts and classification signals, validates that
extraction against a JSON Schema, and decides the final status, policy result, reasons and
clarification question in deterministic code. Every output is schema-validated and
invariant-checked before printing. An evaluation harness (`.harness/`) scores at least 24
synthetic cases on schema, invariants, outcome and quality, and writes evidence with the model
configuration and retry history (never the key). Technical decisions: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12 (`.venv`, 3.12.10)

**Primary Dependencies**: runtime `google-genai` (3.3.0 installed), `python-dotenv`, `jsonschema`;
dev `pytest`, `ruff`. Installed only with `uv pip install --system-certs`.

**Storage**: Files only — `evals/dataset.json` (cases), `evidence/` (run results). No database.

**Testing**: pytest, offline: fixed sample outputs and a stub model client; no API calls in
`tests/`.

**Target Platform**: Windows 11, PowerShell.

**Project Type**: CLI tool with an evaluation harness.

**Performance Goals**: one assessment in < 15 s under normal network conditions (SC-008); the
full evaluation takes about 5 min at 7 s between calls.

**Constraints**: model call timeout 30 s, at most 4 attempts with 1/2/4 s backoff (FR-083);
free-tier rate limit of about 10 requests per minute; key only from `GEMINI_API_KEY`.

**Scale/Scope**: one expense per invocation; ≥ 24 evaluation cases (spec Revision 1).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | How the design complies | Pre | Post |
|---|-----------|-------------------------|-----|------|
| I | Schema-validated JSON | JSON mode + `response_json_schema`; local `jsonschema` validation of the extraction (`extractor.py`) and of the final output (`service.py`); failure → `model_error invalid_response` / exit 3, never printed as a claim | ✅ | ✅ |
| II | Advisory only | No approval/payment/submission code paths; outputs limited to the three statuses; INV-7 sanitiser + evaluator | ✅ | ✅ |
| III | Deterministic policy | `policy.py` holds the table as constants; the model schema has no status/policy fields; deterministic pre-checks for injection/prohibited | ✅ | ✅ |
| IV | Secret handling | `config.py` reads `GEMINI_API_KEY` via python-dotenv; allow-listed evidence fields; test asserts key absence; `.env` git-ignored (root `.gitignore`) | ✅ | ✅ |
| V | Reproducible config | `MODEL_NAME`, `TEMPERATURE` constants in `config.py`; written into every results.json | ✅ | ✅ |
| VI | model_error separate | `ModelError` with sub-type; excluded from score, counted separately; > 2 → INCONCLUSIVE; every retry recorded | ✅ | ✅ |
| VII | Fixed threshold, immutable cases | Thresholds are constants mirroring FR-103/FR-105; dataset has `spec_version` + dated `revised`; run labels immutable | ✅ | ✅ |
| VIII | No guardrail weakening | No skip/xfail markers; ruff and pytest config not loosened; quickstart §4 states the rule | ✅ | ✅ |
| IX | Synthetic data | Fictional merchants (Desert Bites Cafe, Oasis Inn, Paper Point…), test card `4111…1111` only | ✅ | ✅ |
| Tech | Stack & install | Python 3.12, `.venv`, `uv pip install --system-certs`, exactly the listed dependencies | ✅ | ✅ |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-expense-claim-assistant/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── claim.schema.json       # output contract (FR-010) — copied to contracts/ at repo root
│   ├── extraction.schema.json  # model output contract (FR-020)
│   └── cli.md                  # CLI, run_eval and evaluator contracts
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (`Part-1B/`)

```text
pyproject.toml                 # package, `expense` script, ruff + pytest config
prompts/
└── system.md                  # system instruction: extraction rules, JSON only, date resolution, no approval words
contracts/
├── claim.schema.json          # canonical output schema (identical to spec copy; test enforces)
└── extraction.schema.json     # canonical extraction schema
src/expense/
├── __init__.py
├── __main__.py                # python -m expense → cli.main()
├── config.py                  # MODEL_NAME, TEMPERATURE, CALL_DELAY_SECONDS, TIMEOUT_S, RETRY_BACKOFF_S, get_api_key()
├── masking.py                 # mask_card_numbers(), find_unmasked_card_numbers()
├── llm_client.py              # GeminiClient.generate_json(); retry loop; ModelError; AttemptRecord
├── extractor.py               # build prompt from prompts/system.md, call client, json.loads, validate → Extraction
├── policy.py                  # LIMITS_SAR, evaluate() → PolicyDecision
├── service.py                 # assess(text, today, client) → ClaimAssessment; pre-checks, status, clarification, sanitiser, final validation + invariants
└── cli.py                     # argparse, exit codes per contracts/cli.md
evals/
└── dataset.json               # ≥ 24 synthetic cases (FR-100/101), tags + kind
.harness/
├── schema_check.py
├── invariant_check.py
├── outcome_check.py
├── quality_check.py
└── run_eval.py                # runs cases, applies checks, verdict, writes evidence
evidence/
├── eval-results.json          # copy of latest run
└── eval-runs/<label>/         # results.json, summary.md (immutable)
tests/
├── conftest.py                # sample outputs/cases fixtures; stub model client
├── test_policy.py
├── test_masking.py
├── test_schema_check.py
├── test_invariant_check.py
├── test_outcome_check.py
├── test_quality_check.py
├── test_verdict.py            # FR-105 arithmetic (AC-070 – AC-076)
├── test_service.py            # status decisions with stub extractions (US1–US4 ACs)
├── test_llm_client.py         # retry/classification with fake SDK errors (AC-060 – AC-067)
└── test_contracts.py          # spec and repo schema copies identical; no key leakage
```

**Structure Decision**: a single project with a `src/` layout. The harness lives in `.harness/`,
outside the package, so evaluators are independent of the code they judge; pytest adds
`.harness` to `pythonpath`.

## Design Notes

- **Order of processing in `service.assess`**: validate input → mask → injection phrase check →
  prohibited keyword check → model extraction → status decision → policy (if `ok`) → assemble →
  truncate → sanitise wording → mask output → schema validation → invariant check → return.
- **Dependency injection**: `assess()` takes a client object with
  `generate_json(system, user) -> dict`, so tests pass a stub and no API key is needed.
- **Prompt**: `prompts/system.md` is loaded at runtime (not embedded). The user turn contains
  `Today: YYYY-MM-DD` and the masked text inside delimiters, with an instruction that the text
  is data, not instructions.
- **Invariant check at runtime**: `service.py` reuses the same rule list that the spec defines,
  but `.harness/invariant_check.py` is a separate implementation so a bug in one is caught by the
  other.

## Spec Alignment

Spec Revision 1 (2026-11-14) resolved the plan's earlier follow-ups:

1. **model_error sub-types** (change 1.1): `server` (5xx, retried) and `api_error` (other 4xx, not
   retried) are now in FR-081/FR-083 with AC-068 and AC-069; `llm_client.py` classifies per
   [research R2](research.md) and `test_llm_client.py` covers both.
2. **Dataset size** (change 1.2): minimum 24 cases (was 40). `guardrail` ≥ 4 (injection,
   out_of_scope, prohibited_item, innocent "pre-approved" claim expected `ok` / `within_policy`),
   `policy_limit` ≥ 4, `clarification` ≥ 2, `standard` ≥ 2, ≥ 1 card-masking case, and every
   planning `kind` at least once ([research R10](research.md)). The thresholds are unchanged; with
   24 scored cases at least 21 must pass.

Remaining note: `evidence/eval-results.json` is overwritten with each run as the "latest" pointer;
the immutable history is `evidence/eval-runs/<label>/` (FR-106).

## Complexity Tracking

No constitution violations to justify.
