# Research: Expense Claim Assistant

Phase 0 output for [plan.md](plan.md). Each item: Decision / Rationale / Alternatives considered.
SDK facts below were checked against the installed `google-genai` 3.3.0 in `.venv`.

## R1. Gemini call and JSON mode

- **Decision**: `genai.Client(api_key=...)` → `client.models.generate_content(model=MODEL_NAME,
  contents=<masked user text + today>, config=types.GenerateContentConfig(system_instruction=<prompts/system.md>,
  temperature=0.0, response_mime_type="application/json",
  response_json_schema=<extraction.schema.json>))`. The response text is then parsed with
  `json.loads` and validated locally with `jsonschema` (Draft 2020-12).
- **Rationale**: JSON mode plus a response schema makes valid output likely; local validation is
  the actual gate (Constitution I) and does not trust the server.
- **Alternatives**: free-text prompt + regex extraction (fragile); `response_schema` (OpenAPI
  subset, older field — `response_json_schema` accepts standard JSON Schema). If the API rejects
  a schema keyword (e.g. `oneOf`), fall back to `response_mime_type` only; local validation is
  unchanged.

## R2. Timeouts, retries and error classification (FR-080 – FR-083)

- **Decision**: Disable SDK-level retries (`HttpOptions(timeout=30000,
  retry_options=HttpRetryOptions(attempts=1))`; timeout is in milliseconds) and run our own loop
  in `llm_client.py`: up to 4 attempts, sleeping 1, 2, 4 s between them. Classification:

  | Raised | Sub-type | Retried |
  |--------|----------|---------|
  | `httpx.TimeoutException` | `timeout` | yes |
  | `httpx.TransportError` (connect/read failures) | `network` | yes |
  | `errors.ClientError` with `code == 429` | `quota` | yes |
  | `errors.ServerError` (5xx) | `server` | yes |
  | other `errors.ClientError` (400/401/403/404) | `api_error` | no |
  | empty text / `json.JSONDecodeError` / schema failure | `invalid_response` | no |

  Each attempt is recorded as `{attempt, outcome, error_type, elapsed_ms}`. The SDK can use
  either `httpx` or `httpx2` as transport, so the timeout/transport checks match the exception
  classes of whichever of the two modules is importable (built once at import time).
- **Rationale**: Our own loop makes every attempt visible (clarification Q5, Constitution VI);
  SDK retries would be hidden.
- **Spec alignment**: `server` and `api_error` were added to FR-081/FR-083 by spec Revision 1
  (2026-11-14, change 1.1; AC-068, AC-069), so no failure is misreported as `network`.

## R3. API key handling (Constitution IV, FR-084, FR-085)

- **Decision**: `config.py` calls `dotenv.load_dotenv()` (does not override an existing env var),
  then reads `os.environ.get("GEMINI_API_KEY")`. The key is passed straight to `genai.Client` and
  never stored on any object that is logged, serialised or included in `repr`. The
  `ModelError` message contains only the sub-type and HTTP status, never request headers.
  `run_eval.py` writes an explicit allow-list of config fields. A unit test asserts that a fake
  key value does not appear in any evidence file or error message.
- **Rationale**: Allow-listing is safer than trying to scrub secrets out afterwards.
- **Alternatives**: key in a config file (forbidden by the constitution).

## R4. Free-tier rate limiting

- **Decision**: `config.CALL_DELAY_SECONDS = 7.0`, applied between consecutive model calls in
  `run_eval.py` only (the CLI makes one call). Recorded in results.
- **Rationale**: The free tier for `gemini-2.5-flash` allowed about 10 requests per minute (the same pacing is kept for `gemini-3.5-flash`, spec Revision 4); 7 s
  keeps a 24-case run (~3 min) under that limit, so 429 retries stay rare.
- **Alternatives**: rely on 429 retries alone (1+2+4 s backoff is too short for a per-minute
  window, risking `quota` model_errors and an INCONCLUSIVE run).

## R5. Deterministic pre-checks before the model call

- **Decision**: After masking, run the FR-031 injection phrase check and the FR-033 prohibited
  keyword check on the input (case-insensitive, word-boundary regexes). A hit returns
  `rejected` **without calling the model**. Otherwise the model's signals are combined with the
  checks (OR).
- **Rationale**: Saves quota, removes model_error risk for the highest-stakes guardrail cases,
  and guarantees FR-030/FR-033 regardless of model behaviour.
- **Consequence (accepted in spec Revision 2, change 2.1)**: a prohibited keyword match outranks
  `out_of_scope` and model-only injection signals, e.g. "Write me a poem about beer" →
  `prohibited_item` (AC-051). The FR-031 phrase check still runs first.
- **Note**: "pre-approved" does not match any FR-031 phrase (`approve this`, `approve it`,
  `mark as approved` …) — the innocent "pre-approved" evaluation case checks for false positives.

## R6. Wording sanitiser (INV-7, FR-072)

- **Decision**: After the output is assembled, every free-text field goes through a whole-word,
  case-insensitive replacement: `approved` → `cleared`, `paid` → `spent` (so `pre-approved`
  becomes `pre-cleared`). The prompt also tells the model to avoid those words. Rejected outputs
  use fixed descriptions (R7).
- **Rationale**: Deterministic; the evaluator re-checks INV-7 independently.

## R7. Fixed text for rejected outputs

- **Decision**: `description` for rejected claims is fixed per reason:
  `prompt_injection` → "Request contains instructions to change the assistant's rules";
  `out_of_scope` → "Request is not an expense claim"; `prohibited_item` → "Expense is a
  prohibited item under company policy".
- **Rationale**: FR-034 needs a neutral summary; fixed text cannot repeat injected content or
  imply approval.

## R8. Masking (FR-065, FR-070, FR-071)

- **Decision**: Regex `(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)` finds 13–19 digits with optional
  single space/hyphen separators; each match is replaced with `"*" * (n-4) + last4` (separators
  removed). Applied to the input before the model call and to every output string after assembly.
  The evaluator uses the same pattern for detection but its own implementation.
- **Rationale**: Covers the common `4111 1111 1111 1111` and `4111-1111-…` forms. The 13-digit
  minimum avoids masking amounts and dates.

## R9. Evaluation runner design

- **Decision**: `run_eval.py` calls `expense.service.assess()` in-process for each case (no
  subprocess), using the same code path as the CLI. Each case's model_error is caught and
  recorded. Evaluators are pure functions `check(case, output) -> CheckResult`. Verdict per
  FR-105.
- **Evidence layout**: `evidence/eval-runs/<label>/results.json` (full record) and
  `summary.md` are immutable — the run refuses if `<label>` already exists (default label:
  `YYYYMMDD-HHMMSS`). `evidence/eval-results.json` is a copy of the latest run's results, kept
  for convenience; history lives in `eval-runs/` (satisfies FR-106 "never overwriting earlier
  runs").
- **Recorded metadata**: model, temperature, call delay, timeout, retry policy, `google-genai`
  version (`importlib.metadata`), Python version, dataset path + SHA-256, thresholds, git commit
  hash if available. Never the key.

## R10. Dataset size

- **Decision**: `evals/dataset.json` holds **at least 24 cases** (spec Revision 1, change 1.2)
  meeting the FR-101 tag minimums: `guardrail` ≥ 4 (injection, out_of_scope, prohibited_item,
  innocent "pre-approved" claim), `policy_limit` ≥ 4, `clarification` ≥ 2, `standard` ≥ 2, plus
  ≥ 1 card-masking case. Each case also carries a `kind` (normal, boundary, ambiguous,
  missing_info, malformed, policy_limit, adversarial), and every kind appears at least once.
- **Rationale**: 24 cases fit the free-tier daily request budget with room for re-runs and
  retries, and every expected value can be checked by hand. Cases can't be removed later
  (Constitution VII), so the set is fixed carefully from the start. With 24 scored cases, at
  least 21 must pass to reach 85%.

## R11. Packaging and tooling

- **Decision**: `pyproject.toml` (setuptools, `src/` layout) with `[project.scripts] expense =
  "expense.cli:main"`, editable install `uv pip install --system-certs -e .`. Ruff config in
  `pyproject.toml` (`target-version = "py312"`, `line-length = 100`, rules `E,F,W,I,B,UP`).
  pytest `pythonpath = [".harness"]` so tests can import the evaluators.
- **Rationale**: Gives the exact `expense "<text>" --today …` command required by FR-001 while
  `python -m expense` also works.
