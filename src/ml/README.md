# Fraud/Risk ML (Phase 4)

```
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m src.ml.train
```

Trains a logistic-regression baseline and an XGBoost main model on the transactions
currently loaded (`docs/project-status.md` § Phase 3 detail), evaluates both on a temporal
val/test split, computes SHAP global feature importance, and writes
`data/reports/fraud_model_evaluation.json` (committed — small aggregate stats, no raw data).

## Modules

- `dataset.py` — loads `transactions`/`customers`/`complaints`/`daily_exchange_rates` from
  Postgres; computes the temporal train/val/test split proportionally from whatever date range
  is actually loaded (not a hardcoded calendar assumption — Phase 3 only loads a bounded
  sample); `diagnose_fraud_score_separation` is a diagnostic-only query, never a feature.
- `features.py` — leakage-safe feature engineering. Every rolling/historical statistic is
  computed strictly prior to the row it's attached to. See its module docstring for the full
  leakage-prevention rationale and `FEATURE_COLUMNS`/`NOT_IMPLEMENTED_FEATURES` for exactly
  what is and isn't computed.
- `baseline.py` — logistic regression (imputed, scaled, class-balanced).
- `model.py` — XGBoost, with `scale_pos_weight` for the dataset's severe class imbalance;
  `ModelArtifact` carries `model_version`/`feature_version`/`trained_at` on every prediction
  (docs/decision-policy.md § 9).
- `evaluate.py` — precision/recall/F1/ROC-AUC/PR-AUC/FPR/FNR/calibration/confusion matrix
  (docs/evaluation-plan.md § 2). Business-cost metrics are deliberately not computed — no
  business-approved cost coefficients exist in this project (docs/evaluation-plan.md § 3).
- `explain.py` — SHAP global feature importance (per-case explanation is a Phase 10 UI concern).
- `train.py` — CLI orchestrating all of the above into one evaluation report.
- `score.py` (Phase 15, beyond the original roadmap) — scores one live transaction with the
  trained artifact this module produces, finally consulted at live decision time
  (`src/orchestration/live_case.py`). See `docs/project-status.md` § Phase 15 detail for the
  full story, including the real, honestly-measured finding that wiring it in had zero effect
  on the Phase 11 evaluation given this model's own near-chance score distribution (below).

## Result (2026-09-26, 90-day sample, `docs/project-status.md` § Phase 4 detail)

**Both models perform near chance** (ROC-AUC 0.46–0.50) on this sample — reported as a real
finding, not tuned away, per `docs/implementation-roadmap.md` Phase 4's own anticipated risk
("the synthetic `is_fraud` label distribution may be unrealistic ... report this honestly").

This was verified to not be a pipeline bug: none of the 15 implemented features show a
meaningful univariate difference between fraud and non-fraud transactions (checked directly —
see `docs/project-status.md` § Phase 4 detail for the numbers), while the dataset's own
`fraud_score` field (excluded as a feature per the leakage policy, `docs/data-lineage.md` § 5)
*does* separate the classes clearly (mean 15.0 vs. 50.8). A real signal exists in the
generator's process; it isn't exposed through the transactional/behavioral columns this phase
loaded. Leading hypothesis: it lives in device/session/IP data (`digital_events` ->
`Device` derivation, Phase 5), which this ingestion run skipped for memory reasons
(`src/ingestion/README.md`). **Next step if pursuing this further: load `digital_events` for
the same window and add device/IP-novelty features (Phase 5's job), then re-run this exact
pipeline** — everything here is already wired to accept new columns in `FEATURE_COLUMNS`.

## Two real bugs found and fixed during verification (see git history / regression tests)

1. **Currency-scale mixing:** falling back to the raw `amount` column (mixing ARS/COP/MXN/USD,
   which differ by orders of magnitude — observed COP avg ~6.7M vs. USD avg ~1.7k) instead of
   converting via `daily_exchange_rates` produced `amount_deviation` values up to ~4×10¹³.
   Fixed in `_convert_to_usd`; regression test:
   `tests/unit/test_ml_features.py::test_non_usd_amount_is_converted_not_used_raw`.
2. **Wrong success code:** the dataset's success `response_code` is the string `"0"`, not
   `"00"` — the original comparison flagged ~95% of transactions as `auth_failed`. Fixed;
   regression test: `test_response_code_zero_is_treated_as_success`.
3. **10-minute runtime:** the first working version used `.groupby(...).transform(lambda s:
   s.expanding()...)` for per-customer statistics — one Python callable invocation per of
   116k customer groups. Rewritten as vectorized cumsum/cumcount/shift arithmetic (no
   `.expanding()`, no per-group lambda): same statistics, ~30 seconds.
