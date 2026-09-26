"""Fraud model training CLI (docs/implementation-roadmap.md Phase 4).

    DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
      uv run python -m src.ml.train

Loads transactions/customers/complaints/exchange_rates from Postgres (Phase
3's ingested sample — docs/project-status.md § Phase 3 detail), builds
leakage-safe features (features.py), computes the temporal train/val/test
split (dataset.py), trains the logistic-regression baseline and the XGBoost
main model, evaluates both on validation and test, computes SHAP global
feature importance, and writes an evaluation report.

This compares baseline vs. main model only (docs/model-evaluation.md § 4)
— the full rules/ML/LLM/hybrid comparison (docs/evaluation-plan.md § 10)
needs the policy engine and orchestration layers and is Phase 11's job.
"""

import argparse
import datetime as dt
import json
from pathlib import Path

import joblib
import pandas as pd

from src.ml import baseline as baseline_module
from src.ml import model as model_module
from src.ml.dataset import (
    compute_split,
    diagnose_fraud_score_separation,
    load_complaints,
    load_customers,
    load_exchange_rates,
    load_transactions,
)
from src.ml.evaluate import evaluate
from src.ml.explain import global_feature_importance
from src.ml.features import FEATURE_COLUMNS, NOT_IMPLEMENTED_FEATURES, build_features
from src.models.base import get_engine


def _split_frames(
    features: pd.DataFrame, split_label: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = features[split_label == "train"]
    val = features[split_label == "val"]
    test = features[split_label == "test"]
    return train, val, test


def run(report_path: Path, model_dir: Path) -> dict:
    started_at = dt.datetime.now(dt.UTC)
    engine = get_engine()

    transactions = load_transactions(engine)
    customers = load_customers(engine)
    complaints = load_complaints(engine)
    exchange_rates = load_exchange_rates(engine)

    features = build_features(transactions, customers, complaints, exchange_rates)

    min_date = features["transaction_date"].min().date()
    max_date = features["transaction_date"].max().date()
    split = compute_split(min_date, max_date)
    split_label = split.label(features["transaction_date"])

    train_df, val_df, test_df = _split_frames(features, split_label)

    x_train, y_train = train_df[FEATURE_COLUMNS], train_df["is_fraud"].astype(int)
    x_val, y_val = val_df[FEATURE_COLUMNS], val_df["is_fraud"].astype(int)
    x_test, y_test = test_df[FEATURE_COLUMNS], test_df["is_fraud"].astype(int)

    baseline_pipeline = baseline_module.train_baseline(x_train, y_train)
    baseline_val = evaluate(
        y_val.to_numpy(), baseline_module.predict_proba(baseline_pipeline, x_val)
    )
    baseline_test = evaluate(
        y_test.to_numpy(), baseline_module.predict_proba(baseline_pipeline, x_test)
    )

    xgb_artifact = model_module.train_xgboost(x_train, y_train, x_val, y_val, FEATURE_COLUMNS)
    xgb_val = evaluate(y_val.to_numpy(), model_module.predict_proba(xgb_artifact, x_val))
    xgb_test = evaluate(y_test.to_numpy(), model_module.predict_proba(xgb_artifact, x_test))

    feature_importance = global_feature_importance(xgb_artifact.model, x_val, FEATURE_COLUMNS)

    model_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = model_dir / "logistic_regression-baseline.joblib"
    xgb_path = model_dir / f"{xgb_artifact.model_version}.joblib"
    joblib.dump(baseline_pipeline, baseline_path)
    joblib.dump(xgb_artifact, xgb_path)

    report = {
        "run_started_at": started_at.isoformat(),
        "data_window": {"min_date": str(min_date), "max_date": str(max_date)},
        "split": {
            "train": {"start": str(split.train_start), "end": str(split.train_end)},
            "val": {"start": str(split.train_end), "end": str(split.val_end)},
            "test": {"start": str(split.val_end), "end": str(split.test_end)},
            "counts": {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
            "positive_counts": {
                "train": int(y_train.sum()),
                "val": int(y_val.sum()),
                "test": int(y_test.sum()),
            },
        },
        "features": {
            "implemented": FEATURE_COLUMNS,
            "not_implemented": NOT_IMPLEMENTED_FEATURES,
        },
        "models": {
            "baseline": {
                "model_name": "logistic_regression",
                "artifact_path": str(baseline_path),
                "val_metrics_MEASURED": baseline_val.to_dict(),
                "test_metrics_MEASURED": baseline_test.to_dict(),
            },
            "xgboost": {
                "model_name": xgb_artifact.model_name,
                "model_version": xgb_artifact.model_version,
                "feature_version": xgb_artifact.feature_version,
                "artifact_path": str(xgb_path),
                "val_metrics_MEASURED": xgb_val.to_dict(),
                "test_metrics_MEASURED": xgb_test.to_dict(),
                "shap_global_feature_importance_MEASURED": feature_importance,
            },
        },
        "business_metrics": "not available — no business-approved cost coefficients exist "
        "in this project (docs/evaluation-plan.md § 3); not fabricated.",
        "diagnostic_fraud_score_separation_by_is_fraud": diagnose_fraud_score_separation(engine),
        "caveats": [
            "Trained on a bounded recent-date sample (docs/project-status.md § Phase 3 "
            "detail), not the full ~19M-row dataset — do not generalize these numbers "
            "beyond this sample.",
            "is_fraud is a SYNTHETIC dataset-generated label (docs/data-lineage.md § 5), "
            "not a real bank's ground truth.",
            "Class imbalance is severe (see split.positive_counts above) — small absolute "
            "counts of positives in val/test make these metrics high-variance; treat "
            "point estimates cautiously, especially at the test-set scale.",
            "Both models perform near chance (ROC-AUC ~0.46-0.50) on this sample. The "
            "dataset's own (excluded, diagnostic-only) fraud_score field DOES separate "
            "the classes clearly (see diagnostic_fraud_score_separation_by_is_fraud above) "
            "— so a real underlying signal exists in the generator's process, but it is "
            "not exposed through the transactional/behavioral columns this phase loaded. "
            "Leading hypothesis: the signal lives in device/session/IP data "
            "(digital_events -> Device derivation, Phase 5), which this ingestion run "
            "deliberately skipped for memory reasons (src/ingestion/README.md). This is "
            "reported as a real finding, not tuned away — see "
            "docs/implementation-roadmap.md Phase 4's own anticipated risk.",
        ],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def _print_summary(report: dict) -> None:
    print(f"\nData window: {report['data_window']}")
    print(f"Split counts: {report['split']['counts']}")
    print(f"Positive counts: {report['split']['positive_counts']}")
    for name in ("baseline", "xgboost"):
        m = report["models"][name]["test_metrics_MEASURED"]
        print(
            f"\n{name} (test, MEASURED, n={m['sample_size']}, positives={m['positive_count']}):"
            f"\n  precision={m['precision']:.3f} recall={m['recall']:.3f} f1={m['f1']:.3f}"
            f"\n  roc_auc={m['roc_auc']:.3f} pr_auc={m['pr_auc']:.3f}"
            f"\n  fpr={m['false_positive_rate']:.4f} fnr={m['false_negative_rate']:.4f}"
        )
    print("\nTop 5 SHAP features (xgboost, val set):")
    for row in report["models"]["xgboost"]["shap_global_feature_importance_MEASURED"][:5]:
        print(f"  {row['feature']}: {row['mean_abs_shap']:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-path", type=Path, default=Path("data/reports/fraud_model_evaluation.json")
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("data/models"),
        help="Where to save trained model artifacts (git-ignored — binary, not committed).",
    )
    args = parser.parse_args()
    report = run(args.report_path, args.model_dir)
    _print_summary(report)
    print(f"\nFull report written to {args.report_path}")
    print(f"Model artifacts written to {args.model_dir}")


if __name__ == "__main__":
    main()
