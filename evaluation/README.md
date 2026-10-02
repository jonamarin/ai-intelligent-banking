# System Evaluation (Phase 11)

```
docker compose up -d db
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m evaluation.run
```

Implements `docs/evaluation-plan.md` § 9's `python -m evaluation.run` — model, business,
LLM/agent, fairness, reliability, and (the "central piece of evidence," § 10) the four-way
baseline comparison, every number labeled `MEASURED`/`SIMULATED`/`"not available"` per § 1.
Writes `data/reports/evaluation_report.json` (committed — small aggregate stats, no raw
customer data, consistent with every other phase's `data/reports/*.json`).

## Modules

- `sample.py` — builds the **one** held-out sample every approach in `baselines.py` is
  compared against (§ 10: "same held-out workload"). Drawn from Phase 4's own temporal test
  split, further restricted to the `digital_events` window so the Evidence Engine's
  device-history signal isn't trivially `Unknown`. Deliberately oversamples the rare fraud
  class (every in-window fraud transaction + a random legit sample) — severe class imbalance
  (~0.09%) makes a uniform sample this size meaningless otherwise; stated explicitly, not
  silently presented as natural prevalence. Since Phase 15, also primes `src/ml/score.py`'s
  live-scoring cache with the features table it already builds (`prime_cache`) — one feature
  build, not two — so every `EvalCase.case_input` carries a real `fraud_model_score`.
- `baselines.py` — the four approaches: **Rules only** (a fixed threshold stack over the same
  engineered features the ML model trains on — no fitting), **Fraud ML only** (the trained
  XGBoost model, Phase 4, no evidence/policy/human), **LLM only** (`MockLLMClient` called
  directly, bypassing the Policy Engine entirely — deliberately unsafe in the way the hybrid
  design exists to avoid), **Hybrid** (the actual `run_case()` + Policy Engine pipeline built in
  Phases 6-9, now including the fraud ML score — Phase 15).
- `fairness.py` — Hybrid outcome rates by `country`/`segment`, with a stated minimum subgroup
  size below which a subgroup is reported as `"insufficient sample size"` rather than a
  meaningless point estimate.
- `report.py` — assembles everything; `run.py` — the CLI.

## The four-way comparison, and a real finding about wiring in the fraud score

**"Hybrid" is Evidence Engine + Policy Engine + mock LLM + Human + the trained Fraud ML
model's score** — the pre-existing gap this section used to flag (the score was never wired
into orchestration at all, since Phase 4) is now closed (Phase 15, `src/ml/score.py`,
`docs/project-status.md` § Phase 15 detail). **Re-running this exact comparison after wiring it
in produced the identical numbers below** — not because the wiring is inert, but because every
`fraud_model_score` on this sample falls in a narrow band (~0.3997–0.5274) that never crosses
either configured risk-escalation threshold (0.70/0.90), a direct, measured consequence of this
model performing near chance. The mechanism itself is real and unit-tested with a manufactured
score (`tests/unit/test_action_risk.py`, `tests/unit/test_authorization.py`); it simply has zero
measured effect here given this model's actual score distribution.

**A real, non-obvious finding from actually running this**: on the live sample, "LLM only" and
"Hybrid" produce **identical** precision/recall and flagged sets. This isn't a bug — the Policy
Engine never changes *which* action gets proposed, only *whether human approval is
independently required*. The metric that actually shows the Policy Engine's effect is
`policy_engine_override_rate`: the share of cases where the mock LLM's own recommendation
needed no human approval, but the Policy Engine's fact-derived classification forced it anyway
(`docs/decision-policy.md` § 2, Scenario D). **Measured result: 19/152 (12.5%)** — found in real
data, not manufactured for the demo, and exactly the scenario
`tests/unit/test_evaluation.py::test_hybrid_outcome_forces_human_approval_llm_alone_would_not_require`
regression-tests directly.

## Verified result (2026-09-27; Hybrid row re-verified unchanged 2026-10-01, Phase 15)

Full run against the live database, `--legit-sample-size 120` (default), sample size 152
(32 fraud + 120 legit, in-window):

| Approach | precision | recall | f1 | automation_rate |
|---|---|---|---|---|
| 1. Rules only | 0.255 | 0.375 | 0.304 | 0.691 |
| 2. Fraud ML only | 0.230 | 0.531 | 0.321 | 0.513 |
| 3. LLM only (mock) | 0.195 | 0.250 | 0.219 | 0.730 |
| 4. Hybrid (current implementation, now including the fraud ML score — Phase 15) | 0.195 | 0.250 | 0.219 | 0.730 |

`policy_engine_override_rate`: 19/152 (0.125). `groundedness_rate` (flagged decisions citing a
real policy source): 41/41 (1.0). `prompt_injection_resistance`: 0/18 unsafe actions (cited
from Phase 8's adversarial suite, now including the Phase 12 golden case, not re-derived).
`reliability`: 23/23 tests passed (cited from Phase 9). Fairness
by country: all three countries (Argentina n=26, Colombia n=42, México n=84) cleared the
minimum subgroup size and show real, if noisy, escalation-rate/FPR/FNR differences — read as
directional, not conclusive, given the small subgroup sizes (`docs/model-evaluation.md` § 13).

**None of these numbers should be read as "the hybrid approach is better."** The sample is
small (152 cases, deliberately fraud-oversampled), and the Fraud ML model itself performs near
chance on this dataset (`src/ml/README.md`) — which is exactly why wiring its score into the
"Hybrid" row (Phase 15) changed nothing measurable here. What this run *does* demonstrate, with
real numbers: the four approaches behave
differently and measurably (not identically, except for the LLM-vs-Hybrid case explained
above), the Policy Engine has a real, non-zero, measured effect independent of the LLM's own
judgment, and every claim here carries its actual sample size — `docs/evaluation-plan.md` § 11's
requirement, not an aspiration.

## Business metrics: "not available," not fabricated

`docs/evaluation-plan.md` § 3's Expected Loss formula needs cost coefficients (fraud loss,
false-positive cost, customer friction cost, human-agent cost, AI/infrastructure cost) that no
policy owner has supplied. `business_metrics` in the report says `"not available"` with the
reason, per § 9's explicit instruction — never a fabricated dollar figure
(`CLAUDE.md` § 7). Each baseline's `automation_rate` is reported as an unpriced structural
proxy for "human agent cost avoided" instead.

## What this phase does not do

Full-dataset evaluation (still the bounded recent-date sample every prior phase used). A judge
LLM for explanation quality (`docs/evaluation-plan.md` § 12 — not attempted; no rubric exists to
validate one against). Drift monitoring, regression-test-on-every-change automation
(`docs/model-evaluation.md` § 9-10, still `PLANNED`). A statistically powered fairness claim —
152 cases across 3 countries is enough for a directional read, not a significance test.
