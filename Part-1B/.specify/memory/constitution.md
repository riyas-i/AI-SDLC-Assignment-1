<!--
Sync Impact Report — change history (append a new dated entry on every amendment; keep old ones)

## 2026-11-14 — v1.0.0 (initial ratification)
- Version change: (unversioned template) → 1.0.0
- Modified principles: all template placeholders replaced (initial ratification)
  - [PRINCIPLE_1_NAME] → I. Schema-Validated JSON Output (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Advisory Only — No Approval, Payment or Submission
  - [PRINCIPLE_3_NAME] → III. Deterministic Policy Enforcement
  - [PRINCIPLE_4_NAME] → IV. Secret Handling
  - [PRINCIPLE_5_NAME] → V. Reproducible Model Configuration
- Added principles: VI. Model Errors Are Not Evaluation Failures,
  VII. Fixed Evaluation Threshold and Immutable Cases,
  VIII. No Guardrail Weakening by the Coding Agent, IX. Synthetic Test Data Only
- Added sections: Technology & Environment Constraints; Development Workflow & Quality Gates
- Removed sections: none
- Templates: dependent templates read the constitution at runtime; not modified by this command
- Follow-up TODOs: none
-->

# Expense Claim Assistant Constitution

## Core Principles

### I. Schema-Validated JSON Output (NON-NEGOTIABLE)

- The model MUST be instructed to return JSON only (no prose, no Markdown fences).
- Every model output MUST be parsed and validated against the declared output JSON Schema
  (via `jsonschema`) before any downstream use.
- Output that fails parsing or schema validation MUST NOT be treated as a valid claim
  assessment; it MUST be surfaced as an invalid response (see Principle VI).

Rationale: LLM output is untrusted input; a schema gate is the only reliable boundary between
free-form generation and program logic.

### II. Advisory Only — No Approval, Payment or Submission

- The assistant MUST NOT approve, pay, submit or otherwise act on a claim in any system.
- Its only permitted outcomes are: a structured claim assessment, a clarification question,
  or a rejection.
- No code path, tool call or integration that performs approval, payment or submission may be
  added.

Rationale: Financial decisions remain with accountable humans; the assistant's role is
triage and explanation.

### III. Deterministic Policy Enforcement

- Company policy limits (amounts, categories, required fields, etc.) MUST be defined in the
  feature spec.
- Those limits MUST be enforced by deterministic Python code that runs on every assessment;
  the model's judgement alone MUST NOT decide whether a policy limit is met.
- Where the model's output conflicts with deterministic policy checks, the deterministic
  result prevails.

Rationale: Policy compliance must be testable, repeatable and auditable, which model output
alone is not.

### IV. Secret Handling

- The Gemini API key MUST be read only from the `GEMINI_API_KEY` environment variable,
  optionally loaded from a local `.env` file via `python-dotenv`.
- `.env` MUST be listed in `.gitignore` and MUST NOT be committed.
- The key MUST NOT be logged, printed, included in error messages, written to evaluation
  results, or hard-coded anywhere in source, tests or docs.

Rationale: Leaked credentials are an immediate security and cost risk.

### V. Reproducible Model Configuration

- The model name (`gemini-2.5-flash`) and temperature MUST be fixed in a single configuration
  location, not scattered or overridden ad hoc.
- Every evaluation result MUST record the model name and temperature used.

Rationale: Evaluation results are only comparable when the configuration that produced them
is known.

### VI. Model Errors Are Not Evaluation Failures

- API/model errors — timeout, quota exhaustion, network failure, invalid or non-schema
  response — MUST be reported with status `"model_error"`.
- `model_error` MUST be counted and reported separately from evaluation failures
  (wrong outcome against expected result) and MUST NOT be silently retried into a pass or
  dropped from totals.

Rationale: Distinguishing infrastructure faults from behavioural faults keeps evaluation
results honest and diagnosable.

### VII. Fixed Evaluation Threshold and Immutable Cases

- The evaluation pass threshold MUST be declared in the spec before evaluation is run.
- The threshold MUST NEVER be lowered.
- Evaluation cases MUST NOT be deleted.
- Expected results MUST NOT be changed except through a dated spec revision that records
  what changed and why.

Rationale: Moving the goalposts after seeing results invalidates the evaluation.

### VIII. No Guardrail Weakening by the Coding Agent

- The coding agent MUST NOT disable guardrails, weaken schema or policy checks, loosen lint
  or test configuration, skip or mark tests as expected-fail, or remove failing cases in order
  to obtain a PASS.
- A failing check MUST be reported as failing; fixes MUST address the underlying behaviour.

Rationale: A PASS achieved by weakening checks is a false signal and defeats the harness.

### IX. Synthetic Test Data Only

- All test and evaluation data MUST be synthetic.
- Data MUST NOT contain real personal names, employee IDs, payment card numbers, or real
  company data.

Rationale: Avoids privacy and confidentiality exposure in a repository and in model prompts.

## Technology & Environment Constraints

- Language: Python 3.12.
- Platform: Windows with PowerShell; a project virtual environment at `.venv`.
- Package installation MUST use `uv pip install --system-certs` only.
- Runtime dependencies: `google-genai`, `python-dotenv`, `jsonschema`. Adding another runtime
  dependency requires a justified spec/plan change.
- Development tools: `pytest`, `ruff`.
- Model provider: Google Gemini API, model `gemini-2.5-flash`.

## Development Workflow & Quality Gates

- Before evaluation: the spec declares policy limits, the output schema, the evaluation cases
  with expected results, and the pass threshold.
- Gates that MUST pass before work is considered complete: `ruff` checks clean, `pytest`
  green, and the evaluation run meeting the declared threshold with `model_error` cases
  reported separately.
- Unit tests for schema validation and deterministic policy enforcement MUST NOT depend on
  live API calls.
- Changes to the threshold, cases or expected results follow Principle VII; any such change
  is visible in the spec's revision history.

## Governance

- This constitution supersedes other project practices; where a plan, task or generated code
  conflicts with it, the constitution prevails.
- Amendments require: an edit to this file, a Sync Impact Report, a version bump, and an
  updated Last Amended date.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle,
  MINOR for adding a principle/section or materially expanding guidance, PATCH for
  clarifications and wording.
- Every spec, plan, task list and review MUST check compliance with these principles;
  any deviation MUST be documented and justified, or rejected.

**Version**: 1.0.0 | **Ratified**: 2026-11-14 | **Last Amended**: 2026-11-14
