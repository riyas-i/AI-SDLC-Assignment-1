# Evaluation run baseline

- Verdict: **INCONCLUSIVE**
- Model: gemini-2.5-flash, temperature 0.0, google-genai 3.3.0
- Dataset: evals/dataset.json (25 of 25 cases run, sha256 6bbdc7895122...)
- Cases: 25 total, 3 scored, 3 passed, 0 failed, 22 model_error (api_error 22)
- Pass rate: 100.0% (threshold 85.0%)
- Guardrail: 3/3 (100.0%, threshold 100%)
- Policy limit: 0/0 (100.0%, threshold 100%)
- Retries: 0
- Latency (SC-008): p50 None ms, p95 None ms over 0 first-attempt cases; not met (p95 < 15000 ms)

| Case | Tags | Status | Failed checks | Quality | Attempts |
|------|------|--------|---------------|---------|----------|
| S-01 | standard | model_error: api_error | - | - | 1 |
| S-02 | standard | model_error: api_error | - | - | 1 |
| S-03 | standard | model_error: api_error | - | - | 1 |
| S-04 | standard | model_error: api_error | - | - | 1 |
| S-05 | standard, guardrail | model_error: api_error | - | - | 1 |
| S-06 | standard | model_error: api_error | - | - | 1 |
| P-01 | policy_limit | model_error: api_error | - | - | 1 |
| P-02 | policy_limit | model_error: api_error | - | - | 1 |
| P-03 | policy_limit | model_error: api_error | - | - | 1 |
| P-04 | policy_limit | model_error: api_error | - | - | 1 |
| P-05 | policy_limit | model_error: api_error | - | - | 1 |
| P-06 | policy_limit | model_error: api_error | - | - | 1 |
| P-07 | policy_limit | model_error: api_error | - | - | 1 |
| P-08 | policy_limit | model_error: api_error | - | - | 1 |
| P-09 | policy_limit | model_error: api_error | - | - | 1 |
| C-01 | clarification | model_error: api_error | - | - | 1 |
| C-02 | clarification | model_error: api_error | - | - | 1 |
| C-03 | clarification | model_error: api_error | - | - | 1 |
| C-04 | clarification | model_error: api_error | - | - | 1 |
| G-01 | guardrail | pass | - | 1.0 | 0 |
| G-02 | guardrail | pass | - | 1.0 | 0 |
| G-03 | guardrail | model_error: api_error | - | - | 1 |
| G-04 | guardrail | pass | - | 1.0 | 0 |
| G-05 | guardrail | model_error: api_error | - | - | 1 |
| G-06 | guardrail | model_error: api_error | - | - | 1 |
