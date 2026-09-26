# Model Evaluation

Owns: ML- and LLM-specific evaluation methodology. See `docs/evaluation-plan.md` for the
system-level metric categories and outcome taxonomy this document's methods feed into.

## 1. Dataset strategy

Source: LATAM Bank Dataset (`docs/data-dictionary.md`), specifically `transactions` (5M rows,
`is_fraud`/`fraud_score` present) joined to `customers`, `products`, `digital_events`
(device/session context), and `complaints` (customer-reported disputes). Data spans June 2023
– June 2026 (`docs/data-lineage.md` § Source). The raw dataset files are not present in this
repository as of this initialization — ingestion is `PLANNED` (Phase 3,
`docs/implementation-roadmap.md`).

## 2. Temporal splitting (leakage prevention)

Fraud is time-dependent; a random split leaks future information into training. Split by
transaction date, following the dataset's own three-year span, e.g.:

```
TRAIN:      earlier period   (e.g., first ~18 months)
VALIDATION: middle period    (e.g., next ~9 months)
TEST:       final period     (e.g., most recent ~9 months, closest to "now")
```

Exact cut points are `TBD` until the actual date distribution of `transactions` is profiled
(row counts may not be uniform across the range) — do not hardcode calendar quarters without
checking the real distribution first. Document the chosen split and the reasoning once set.

## 3. Leakage prevention beyond splitting

- **`fraud_score` on `transactions` is excluded from model features.** It is very likely
  itself a prior model's or the data generator's output; using it as an input would leak the
  answer into the features. It may be used only as a labeled-`SYNTHETIC` reference point in
  evaluation writeups, never as a training feature.
  Never train on any field that would not have been known before the transaction completed.
- Ensure a customer's later transactions/complaints don't influence engineered features for
  earlier transactions (e.g., a rolling average must only look backward).

## 4. Baseline models

1. **Rule-based / logistic-regression baseline** — simple, interpretable, cheap; the floor the
   main model must beat.
2. **Main model** — XGBoost or LightGBM on tabular features (`prompt.md` § 11):
   transaction-amount deviation from customer historical average, transaction velocity,
   country deviation, device novelty, IP novelty, merchant risk, authentication result,
   card-present status (derived — see `docs/domain-model.md` § Transaction), time-of-day
   deviation, transaction frequency, historical dispute rate (from `complaints`), geographic
   distance, recent transaction count. Every feature must be documented (name, source table,
   derivation, and why it isn't leakage) before it's used.

## 5. Feature validation

`PLANNED`: schema and range checks on every engineered feature (no negative amounts where
invalid, no future timestamps, currency consistency using `daily_exchange_rates`), plus a
feature-distribution sanity check before training (`docs/data-governance.md` § Data Quality).

## 6. Model calibration and explainability

Report calibration (are predicted probabilities close to observed frequencies), not just
discrimination (AUC). Use SHAP for feature-level explainability, feeding the analyst-facing
explanation (`prompt.md` § 22) — the technical explanation must be able to cite the top
contributing features, not just the score.

## 7. Model and prompt versioning

Every model prediction carries `model_name`, `model_version`, `feature_version`, `timestamp`.
Every LLM decision carries `provider`, `model`, `prompt_version`, `policy_version`
(`prompt.md` § 54) — required for the decision-provenance chain in `docs/decision-policy.md`
§ 9.

## 8. LLM evaluation

Separate from ML evaluation: evaluate the LLM's intent/entity extraction accuracy, its
groundedness (does an explanation cite retrieved evidence rather than invent content), tool-
call correctness (did it request the right tool with valid arguments), and its refusal/safety
behavior on adversarial input (`docs/guardrails.md` § Red-Team Cases). Golden cases and
adversarial cases live in `evaluation/golden_cases/` (schema documented there).

## 9. Regression tests and drift monitoring

`PLANNED`: a fixed regression suite (golden cases) run on every prompt or model change before
it ships; drift monitoring compares live feature/prediction distributions against the training
distribution over time. Neither exists yet — record as `NOT_IMPLEMENTED` in
`docs/project-status.md` until built.

## 10. Drift categories to watch

Data drift, concept drift, label drift, feature drift, fraud-pattern drift, model drift,
prompt drift, LLM behavior drift, policy drift (`prompt.md` § 24). Detection approach for each
is `PLANNED`, not implemented — this document records the taxonomy so the implementation phase
doesn't have to rediscover it.

## 11. Versioning and rollback

Version models, prompts, policies, schemas, feature definitions, and evaluation datasets
independently, so any of them can be rolled back without forcing a redeploy of the others.
Reproducibility requirement: a past decision should be reconstructable from its recorded
`model_version`/`prompt_version`/`policy_version`/`feature_version` whenever the corresponding
artifact is still retained (`docs/decision-policy.md` § 9).

## 12. Rules vs. ML vs. LLM vs. hybrid (conceptual comparison)

| Approach | Strength | Weakness |
|---|---|---|
| Rules only | Deterministic, cheap, auditable | Brittle, poor contextual understanding |
| ML only | Scalable, measurable | Weak conversational interaction, weaker natural-language explanations |
| LLM only | Flexible, contextual | Expensive, slower, less deterministic, unsafe for critical actions if given direct authority |
| Hybrid (this project) | Uses each mechanism where it's strongest | More components to build, test, and keep consistent |

This table is architectural reasoning, not a measured result — `docs/evaluation-plan.md` § 10
owns the actual baseline comparison methodology, and only a completed run can support a
superiority claim for the hybrid approach.

## 13. Fairness methodology

Compare outcome rates (§ `docs/evaluation-plan.md` § 7) across `country`, `segment`, and
`detected_accent`-derived dialect groups present in the dataset. Sample-size limitations must
be stated per subgroup — some segments/countries will have too few disputed transactions in
the synthetic data for a statistically meaningful comparison; report that honestly rather than
suppressing the subgroup.
