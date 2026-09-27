"""System-level evaluation CLI (`docs/evaluation-plan.md` § 9).

    DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
      uv run python -m evaluation.run

Needs the database (Phase 3+ data loaded) and, for the "Fraud ML only" row,
a trained model artifact (`uv run python -m src.ml.train` first) — if
either is missing, the corresponding section prints `"not available"` with
a stated reason rather than fabricating a result
(`docs/evaluation-plan.md` § 9: "must never fabricate results if a
dependency ... makes a metric unavailable").
"""

import argparse
from pathlib import Path

from evaluation.report import run_evaluation, write_report
from src.models.base import get_engine


def _print_summary(report: dict) -> None:
    print("\n=== Fraud ML metrics (Phase 4, reused) ===")
    ml = report["fraud_ml_metrics"]
    if ml["status"] == "MEASURED":
        xgb = ml["xgboost_test_MEASURED"]
        print(
            f"  xgboost test: roc_auc={xgb['roc_auc']:.3f} pr_auc={xgb['pr_auc']:.3f} "
            f"n={xgb['sample_size']} positives={xgb['positive_count']}"
        )
    else:
        print(f"  {ml['status']}: {ml.get('reason')}")

    print("\n=== Business metrics ===")
    print(f"  {report['business_metrics']['status']}: {report['business_metrics']['reason']}")

    print("\n=== Baseline comparison (docs/evaluation-plan.md § 10) ===")
    bc = report["baseline_comparison"]
    print(f"  sample: {bc['sample']}")
    keys = (
        "1_rules_only",
        "2_fraud_ml_only",
        "3_llm_only_SIMULATED_mock_mode",
        "4_hybrid_current_implementation",
    )
    for key in keys:
        row = bc[key]
        if "status" in row and row["status"] == "not available":
            print(f"  {key}: not available ({row['reason']})")
            continue
        if row["sample_size"] == 0:
            print(f"  {key}: empty sample — no cases to evaluate")
            continue
        print(
            f"  {key}: precision={row['precision']:.3f} recall={row['recall']:.3f} "
            f"f1={row['f1']:.3f} fpr={row['false_positive_rate']:.3f} "
            f"fnr={row['false_negative_rate']:.3f} automation_rate={row['automation_rate']:.3f}"
        )
    po = bc["policy_engine_override_rate"]
    print(f"  policy_engine_override_rate: {po['value']} ({po['numerator']}/{po['denominator']})")
    print(f"  note: {bc['note']}")

    print("\n=== LLM/agent metrics (mock mode) ===")
    llm = report["llm_agent_metrics"]
    g = llm["groundedness_rate"]
    print(f"  groundedness_rate: {g['value']} ({g['numerator']}/{g['denominator']})")
    print(f"  injection_resistance: {llm['prompt_injection_resistance']['value_MEASURED']}")

    print("\n=== Reliability ===")
    print(f"  {report['reliability_metrics']['result_at_last_full_suite_run']}")

    print("\n=== Fairness by country (small-sample — see per-subgroup note) ===")
    for country, outcome in report["fairness_by_country"].items():
        print(f"  {country}: {outcome}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-path", type=Path, default=Path("data/reports/evaluation_report.json")
    )
    parser.add_argument(
        "--legit-sample-size",
        type=int,
        default=120,
        help="Random sample of legitimate in-window transactions to add to every fraud one "
        "(evaluation/sample.py).",
    )
    args = parser.parse_args()

    engine = get_engine()
    report = run_evaluation(engine, legit_sample_size=args.legit_sample_size)
    write_report(report, args.report_path)
    _print_summary(report)
    print(f"\nFull report written to {args.report_path}")


if __name__ == "__main__":
    main()
