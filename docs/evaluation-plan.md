# Evaluation Plan

Owns: system-level evaluation strategy and acceptance process. See `docs/model-evaluation.md`
for ML/LLM-specific methodology (dataset splitting, leakage prevention, golden cases), and
`evaluation/golden_cases/` for the actual fixtures.

## 1. Labeling rule (applies to every metric in this document)

Every number this project reports must be labeled `MEASURED` (from an actual run, with the
command and dataset that produced it), `SIMULATED`/`OFFLINE` (computed outside a live system),
or `PROJECTED` (an estimate, not a measurement). Never describe an offline comparison as a
measured production improvement (`project_presentation.txt` § Evaluation evidence). No target
values in this document are business-approved — they are categories to fill in once a baseline
exists.

## 2. Fraud / ML metrics

Precision, recall, F1, ROC-AUC, PR-AUC, false-positive rate, false-negative rate, calibration,
threshold analysis, confusion matrix. Full methodology (splitting, leakage, baselines):
`docs/model-evaluation.md`.

## 3. Business metrics

Expected loss, fraud loss, false-positive cost, estimated customer friction, human escalation
rate, automation rate, resolution time, human-agent cost, AI/infrastructure cost. The guiding
objective (`prompt.md` § 1):

```
Expected Loss = Fraud Loss + False Positive Cost + Customer Friction Cost
              + Human Agent Cost + AI/Infrastructure Cost
```

This formula is a design objective to make trade-offs explicit — not a validated cost model.
Cost coefficients are `TBD` until a policy owner supplies them; do not invent dollar figures.

## 4. LLM metrics

Groundedness (does the explanation cite retrieved evidence/policy, not invented content),
hallucination rate, tool-call correctness, tool-authorization compliance, policy adherence,
evidence usage, explanation quality, prompt-injection resistance (rate of successful
injections, target: 0).

## 5. System metrics

Latency (p50/p95 per `project_presentation.txt` § Operating efficiency), throughput,
availability, timeout rate, dependency-failure behavior, retry behavior, idempotency
correctness, queue behavior (if an event system is introduced).

## 6. Privacy/security metrics

PII leakage incidents (target: 0), unauthorized access attempts and their outcome, successful
prompt injections (target: 0), tool abuse attempts and outcome, secret exposure incidents
(target: 0), privilege-escalation attempts and outcome.

## 7. Fairness

Where legally and ethically appropriate, compare false-positive rate, false-negative rate,
escalation rate, and automation rate across relevant customer groups available in the dataset
(e.g., `country`, `segment`, `detected_accent` as a proxy for regional dialect — never as a
decision input, only as an evaluation slice). Do not use protected attributes for decision-
making. Document which attributes were used for evaluation, which were excluded from decision
logic and why, and the limitations of the fairness evaluation (small subgroup sample sizes,
synthetic-data artifacts). Never claim fairness without evidence — `docs/model-evaluation.md`
§ Fairness owns the measurement methodology.

## 8. Outcome taxonomy (from the competition brief — used consistently everywhere)

- **Safe automated resolution:** an eligible case reaches the correct, policy-compliant
  outcome with no human intervention. Report the rate over all in-scope test cases, plus the
  share of cases on which automation was attempted.
- **Containment:** a case ends without transfer to a human. Containment alone does not
  demonstrate the problem was solved — never report it as a success metric on its own.
- **Escalation quality:** escalated cases are transferred correctly with useful handoff
  context; report both missed and unnecessary transfers where reference labels permit.
- **Unsafe outcomes:** unauthorized disclosures/actions or materially incorrect outcomes,
  reported with counts and denominators. Zero observed failures in a small test set does not
  establish zero risk — say so explicitly whenever reporting it.
- **Operating efficiency:** end-to-end p50/p95 latency and cost per attempted case and per
  successful automated resolution. State workload, sample size, and cost assumptions; use
  "not defined" rather than a fabricated number when there are no successful resolutions.

(`project_presentation.txt` § Evaluation evidence.)

## 9. Evaluation command

```
python -m evaluation.run
```

`PLANNED` — does not exist yet. Once implemented (Phase 11, `docs/implementation-roadmap.md`),
it must generate fraud metrics, business metrics, fairness metrics, LLM metrics, robustness
metrics, and scenario results from `evaluation/golden_cases/`, and must never fabricate
results if a dependency (e.g., no trained model yet) makes a metric unavailable — print
`not available` for that metric instead.

## 10. Comparison against baselines

Compare, on the same held-out workload (`docs/model-evaluation.md` § Baselines):

1. Rules only
2. Fraud ML only
3. LLM only
4. Proposed hybrid (LLM + ML + Rules + Evidence + Human)

This comparison is the central piece of evidence for why the hybrid architecture exists
(`prompt.md` § 38) — required, not optional, before any claim of the hybrid approach being
"better."

## 11. Held-out evaluation and failure conditions

Evaluate on held-out cases that include incorrect or missing data, expired sessions,
unauthorized access attempts, prompt injection, tool failures, and multilingual ambiguity
(`project_presentation.txt` § Evaluation evidence, item 5). Report successful outcomes, unsafe
outcomes, handoff behavior, latency, and cost together with sample sizes and limitations —
every metric must carry its denominator.

## 12. Judge-model usage

If an LLM is used to judge answers (e.g., explanation quality), its rubric must be documented
and validated against a sample of human or deterministic judgments before being trusted —
`docs/model-evaluation.md` § LLM Evaluation owns this.
