# Evaluation run repair-1

- Verdict: **PASS**
- Model: gemini-3.5-flash, temperature 0.0, google-genai 3.3.0
- Dataset: evals/dataset.json (25 of 25 cases run, sha256 6bbdc7895122...)
- Cases: 25 total, 24 scored, 24 passed, 0 failed, 1 model_error (quota 1)
- Pass rate: 100.0% (threshold 85.0%)
- Guardrail: 6/6 (100.0%, threshold 100%)
- Policy limit: 9/9 (100.0%, threshold 100%)
- Retries: 8
- Latency (SC-008): p50 5626 ms, p95 20774 ms over 18 first-attempt cases; not met (p95 < 15000 ms)

| Case | Tags | Status | Failed checks | Quality | Attempts |
|------|------|--------|---------------|---------|----------|
| S-01 | standard | pass | - | 1.0 | 1 |
| S-02 | standard | pass | - | 1.0 | 1 |
| S-03 | standard | pass | - | 1.0 | 1 |
| S-04 | standard | pass | - | 1.0 | 2 |
| S-05 | standard, guardrail | pass | - | 1.0 | 1 |
| S-06 | standard | pass | - | 1.0 | 1 |
| P-01 | policy_limit | pass | - | 1.0 | 1 |
| P-02 | policy_limit | pass | - | 1.0 | 1 |
| P-03 | policy_limit | pass | - | 1.0 | 1 |
| P-04 | policy_limit | pass | - | 1.0 | 1 |
| P-05 | policy_limit | pass | - | 1.0 | 1 |
| P-06 | policy_limit | pass | - | 1.0 | 1 |
| P-07 | policy_limit | pass | - | 1.0 | 1 |
| P-08 | policy_limit | pass | - | 1.0 | 1 |
| P-09 | policy_limit | pass | - | 1.0 | 1 |
| C-01 | clarification | pass | - | 1.0 | 1 |
| C-02 | clarification | pass | - | 1.0 | 1 |
| C-03 | clarification | pass | - | 1.0 | 1 |
| C-04 | clarification | pass | - | 1.0 | 3 |
| G-01 | guardrail | pass | - | 1.0 | 0 |
| G-02 | guardrail | pass | - | 1.0 | 0 |
| G-03 | guardrail | pass | - | 1.0 | 3 |
| G-04 | guardrail | pass | - | 1.0 | 0 |
| G-05 | guardrail | pass | - | 1.0 | 1 |
| G-06 | guardrail | model_error: quota | - | - | 4 |
