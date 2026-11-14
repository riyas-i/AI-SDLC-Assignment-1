# CLI Contract

## `expense`

```text
expense "<text>" [--today YYYY-MM-DD]
python -m expense "<text>" [--today YYYY-MM-DD]
```

| Outcome | stdout | stderr | Exit |
|---------|--------|--------|------|
| Assessment produced (`ok`, `needs_clarification`, `rejected`) | one JSON object per [claim.schema.json](claim.schema.json), UTF-8, keys in schema order | one line per failed attempt only, e.g. `retry 1/3: network`; empty on a first-attempt success | 0 |
| Usage error (empty/whitespace text, > 1000 chars, bad `--today`) | — | `usage error: <reason>` | 1 |
| `GEMINI_API_KEY` not set | — | `GEMINI_API_KEY is not set` | 1 |
| Model error (after retries per FR-083) | — | `model_error: <timeout\|network\|quota\|server\|api_error\|invalid_response>` | 2 |
| Internal: final output fails schema or invariants | — | `internal_error: <check>` | 3 |

The key value never appears on stdout or stderr.

## `run_eval.py`

```text
python .harness/run_eval.py [--dataset evals/dataset.json] [--label <name>] [--limit N] [--compare-with <label>]
```

| Item | Contract |
|------|----------|
| Writes | `evidence/eval-runs/<label>/results.json`, `evidence/eval-runs/<label>/summary.md`, and a copy at `evidence/eval-results.json` |
| Label | defaults to `YYYYMMDD-HHMMSS`; an existing label is refused (exit 1) |
| `--limit` | debug only; a limited run's verdict is `INCOMPLETE` and is never reported as PASS |
| `--compare-with` | adds a `consistency` block comparing `status`, `policy_result`, `policy_reasons` per case with an earlier run (SC-007); model_error cases in either run are excluded |
| `latency` block | always written: `p50_ms`, `p95_ms` over first-attempt model cases, `sc008_pass` (SC-008) |
| stdout | summary: counts, pass rate, guardrail/policy-limit rates, model_errors, verdict |
| Exit | 0 = PASS, 1 = FAIL, 2 = INCONCLUSIVE, 3 = INCOMPLETE / setup error |
| Results shape | see [data-model.md §8](../data-model.md) |

## Evaluator modules (`.harness/`)

Each exposes `check(case: dict, output: dict | None) -> CheckResult`, as a pure function with no
I/O and no network:

| Module | Pass condition |
|--------|----------------|
| `schema_check.py` | output validates against `contracts/claim.schema.json` |
| `invariant_check.py` | INV-1 … INV-7 (FR-060 – FR-066), using the case's `today` and `nights` |
| `outcome_check.py` | `status`, `rejection_reason`, `policy_result`, `missing_fields` equal expected |
| `quality_check.py` | score = mean(category, amount, date, description fidelity); passed if ≥ 0.8 |
