"""Assembles the full evaluation report (`docs/evaluation-plan.md`) from:
Phase 4's already-measured ML metrics (reused, not re-derived), a fresh
baseline comparison across the four required approaches on one common
held-out sample (`docs/evaluation-plan.md` § 10), LLM/agent metrics
computed from that same sample, fairness metrics sliced by customer
attribute, and citations (not re-derivations) of the Phase 8/9 security and
reliability suites' own measured results.

Every top-level section is labeled per `docs/evaluation-plan.md` § 1 —
`MEASURED` (with the command/sample that produced it), `SIMULATED` (mock
LLM mode, not a real provider), or `"not available"` (never fabricated).
"""

import datetime as dt
import json
from pathlib import Path
from typing import Any

from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sqlalchemy.engine import Engine

from evaluation import baselines, fairness
from evaluation.sample import EvalCase, build_eval_sample, sample_summary
from src.retrieval.policy_rag import PolicyRAG

_XGBOOST_ARTIFACT_PATH = "data/models/xgboost-v0.1.0.joblib"
_PHASE4_REPORT_PATH = "data/reports/fraud_model_evaluation.json"


def binary_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    """Precision/recall/F1/confusion matrix for a hard binary decision — no
    ROC-AUC/PR-AUC (undefined for a single threshold's hard output, unlike
    src/ml/evaluate.py's probability-based `evaluate()`, which the
    "Fraud ML only" row reuses instead — see below)."""
    if not y_true:
        return {
            "sample_size": 0,
            "positive_count": 0,
            "precision": None,
            "recall": None,
            "f1": None,
            "false_positive_rate": None,
            "false_negative_rate": None,
            "confusion_matrix": None,
            "automation_rate": None,
            "note": "empty sample — no cases to evaluate",
        }
    yt = [int(v) for v in y_true]
    yp = [int(v) for v in y_pred]
    tn, fp, fn, tp = confusion_matrix(yt, yp, labels=[0, 1]).ravel()
    return {
        "sample_size": len(yt),
        "positive_count": sum(yt),
        "precision": float(precision_score(yt, yp, zero_division=0)),
        "recall": float(recall_score(yt, yp, zero_division=0)),
        "f1": float(f1_score(yt, yp, zero_division=0)),
        "false_positive_rate": (fp / (fp + tn)) if (fp + tn) else None,
        "false_negative_rate": (fn / (fn + tp)) if (fn + tp) else None,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        # An unpriced stand-in for "human agent cost avoided" (no dollar
        # figure — docs/evaluation-plan.md § 3, no approved cost
        # coefficients exist): the share of this sample NOT flagged, i.e.
        # this approach would resolve it without a human at all.
        "automation_rate": 1 - (sum(yp) / len(yp)) if yp else None,
    }


def _load_phase4_ml_metrics() -> dict[str, Any]:
    path = Path(_PHASE4_REPORT_PATH)
    if not path.exists():
        return {
            "status": "not available",
            "reason": f"{_PHASE4_REPORT_PATH} not found — run `uv run python -m src.ml.train` "
            "first (docs/project-status.md § Phase 4 detail).",
        }
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": "MEASURED",
        "source": _PHASE4_REPORT_PATH,
        "split": report["split"],
        "baseline_logistic_regression_test_MEASURED": report["models"]["baseline"][
            "test_metrics_MEASURED"
        ],
        "xgboost_test_MEASURED": report["models"]["xgboost"]["test_metrics_MEASURED"],
        "caveats": report["caveats"],
    }


def _run_baseline_comparison(cases: list[EvalCase]) -> dict[str, Any]:
    rag = PolicyRAG()
    xgb_artifact = None
    xgb_load_error: str | None = None
    try:
        xgb_artifact = baselines.load_xgboost_artifact(_XGBOOST_ARTIFACT_PATH)
    except FileNotFoundError as exc:
        xgb_load_error = str(exc)

    y_true = [c.is_fraud for c in cases]
    rules_flags: list[bool] = []
    ml_flags: list[bool] = []
    llm_flags: list[bool] = []
    hybrid_records: list[dict[str, Any]] = []
    policy_overrides = 0  # LLM alone would NOT require human approval, but the Policy Engine does

    for case in cases:
        rules_flags.append(baselines.rules_only_flag(case.features))
        if xgb_artifact is not None:
            ml_flags.append(baselines.ml_only_flag(xgb_artifact, case.features))
        llm_outcome = baselines.llm_only_flag(case.case_input)
        llm_flags.append(llm_outcome.flagged)
        hybrid = baselines.hybrid_outcome(case.case_input, rag)
        if not llm_outcome.requires_human_approval and hybrid.requires_human_approval:
            policy_overrides += 1
        hybrid_records.append(
            {
                "transaction_id": case.transaction_id,
                "is_fraud": case.is_fraud,
                "country": case.country,
                "segment": case.segment,
                "proposed_action": hybrid.proposed_action,
                "flagged": hybrid.flagged,
                "policy_source": hybrid.policy_source,
                "authorized": hybrid.authorized,
                "requires_human_approval": hybrid.requires_human_approval,
                "llm_only_requires_human_approval": llm_outcome.requires_human_approval,
            }
        )

    hybrid_flags = [r["flagged"] for r in hybrid_records]

    result: dict[str, Any] = {
        "status": "MEASURED",
        "sample": sample_summary(cases),
        "1_rules_only": binary_metrics(y_true, rules_flags),
        "3_llm_only_SIMULATED_mock_mode": binary_metrics(y_true, llm_flags),
        "4_hybrid_current_implementation": binary_metrics(y_true, hybrid_flags),
        "policy_engine_override_rate": {
            "value": (policy_overrides / len(cases)) if cases else None,
            "numerator": policy_overrides,
            "denominator": len(cases),
            "definition": "share of cases where the mock LLM's own recommendation needed no "
            "human approval, but the Policy Engine's independent, fact-derived action-risk "
            "classification required it anyway (docs/decision-policy.md § 2, Scenario D) — "
            "the actual value the Policy Engine adds over 'LLM only', not visible in the "
            "flagged/precision/recall numbers above because those only track WHICH action was "
            "proposed, and the Policy Engine never changes that, only who may authorize it.",
        },
        "hybrid_records": hybrid_records,
    }
    if xgb_artifact is not None:
        result["2_fraud_ml_only"] = binary_metrics(y_true, ml_flags)
    else:
        result["2_fraud_ml_only"] = {
            "status": "not available",
            "reason": f"{_XGBOOST_ARTIFACT_PATH} not found: {xgb_load_error} — run "
            "`uv run python -m src.ml.train` first.",
        }
    result["note"] = (
        "'4_hybrid_current_implementation' is Evidence Engine + Policy Engine + mock LLM + "
        "Human — the Fraud ML model's score is NOT wired into orchestration (a pre-existing, "
        "already-documented gap, docs/project-status.md § Phase 4/6/7/9 detail), so this is "
        "not yet the full 'Rules + ML + LLM + Evidence + Human' hybrid docs/model-evaluation.md "
        "§ 12 describes. '3_llm_only' calls MockLLMClient directly, bypassing the Policy "
        "Engine entirely — deliberately unsafe in the way the hybrid design exists to avoid; "
        "measuring it is the point. Its precision/recall/flagged-set are identical to the "
        "Hybrid row on this sample BY CONSTRUCTION — the Policy Engine never changes WHICH "
        "action gets proposed, only whether human approval is independently required "
        "(see 'policy_engine_override_rate' for the metric that actually shows the Policy "
        "Engine's effect)."
    )
    return result


def _llm_agent_metrics(hybrid_records: list[dict[str, Any]]) -> dict[str, Any]:
    grounding_relevant = [r for r in hybrid_records if r["flagged"]]
    grounded = [r for r in grounding_relevant if r["policy_source"]]
    authorized_count = sum(1 for r in hybrid_records if r["authorized"])
    return {
        "status": "MEASURED, mock LLM mode (LLM_MODE=mock — no real provider exists in this "
        "project, docs/agents/llm_client.py) — not a measurement of real-LLM quality",
        "groundedness_rate": {
            "value": (len(grounded) / len(grounding_relevant)) if grounding_relevant else None,
            "numerator": len(grounded),
            "denominator": len(grounding_relevant),
            "definition": "share of flagged (protect_account/escalate/create_dispute/refuse) "
            "decisions whose explanation cites a real policy_source (src/retrieval/policy_rag.py)",
        },
        "tool_authorization_pass_rate": {
            "value": (authorized_count / len(hybrid_records)) if hybrid_records else None,
            "numerator": authorized_count,
            "denominator": len(hybrid_records),
            "definition": "share of proposed tool calls the Policy Engine authorized (not "
            "hard-denied) — expected near 1.0 for this sample of fresh, open cases; a lower "
            "number would indicate a real authorization-chain problem",
        },
        "prompt_injection_resistance": {
            "value_MEASURED": "0/18 unsafe actions",
            "source": "tests/security/test_red_team.py::"
            "test_adversarial_suite_unsafe_action_rate_is_zero (Phase 8) — cited here, not "
            "re-derived; re-run `uv run pytest tests/security/ -q -s` to refresh",
        },
    }


def _reliability_metrics() -> dict[str, Any]:
    return {
        "status": "MEASURED (pass/fail test suite, not a sampled rate)",
        "source": "tests/reliability/ (Phase 9) — 23 tests: LLM fallback (Scenario E), bounded "
        "DB-connect timeout (verified against a genuinely unreachable address), RAG-failure "
        "degradation, idempotency-key derivation",
        "command": "uv run pytest tests/reliability/ -q",
        "result_at_last_full_suite_run": "23/23 passed (docs/project-status.md § Phase 9 detail)",
    }


def _business_metrics() -> dict[str, Any]:
    return {
        "status": "not available",
        "reason": "No business-approved cost coefficients exist for the Expected Loss formula "
        "(docs/evaluation-plan.md § 3: Fraud Loss + False Positive Cost + Customer Friction "
        "Cost + Human Agent Cost + AI/Infrastructure Cost) — fabricating dollar figures would "
        "violate CLAUDE.md § 7. Structural proxies computed instead, below.",
        "structural_proxies_MEASURED": "see baseline_comparison's per-approach "
        "'automation_rate' (share of cases resolved without a human) as an unpriced stand-in "
        "for 'human agent cost avoided' — not a dollar figure",
    }


def run_evaluation(engine: Engine, *, legit_sample_size: int = 120) -> dict[str, Any]:
    started_at = dt.datetime.now(dt.UTC)
    cases = build_eval_sample(engine, legit_sample_size=legit_sample_size)

    baseline_comparison = _run_baseline_comparison(cases)
    hybrid_records = baseline_comparison.pop("hybrid_records")

    report: dict[str, Any] = {
        "run_started_at": started_at.isoformat(),
        "fraud_ml_metrics": _load_phase4_ml_metrics(),
        "business_metrics": _business_metrics(),
        "baseline_comparison": baseline_comparison,
        "llm_agent_metrics": _llm_agent_metrics(hybrid_records),
        "reliability_metrics": _reliability_metrics(),
        "fairness_by_country": fairness.fairness_by_attribute(hybrid_records, "country"),
        "fairness_by_segment": fairness.fairness_by_attribute(hybrid_records, "segment"),
        "caveats": [
            "All fairness/baseline-comparison numbers come from one small, deliberately "
            "fraud-oversampled held-out window (see baseline_comparison.sample) — not "
            "representative of natural class prevalence, and too small for anything beyond a "
            "directional read at the subgroup level (docs/model-evaluation.md § 13).",
            "is_fraud is a SYNTHETIC dataset-generated label (docs/data-lineage.md § 5), not a "
            "real bank's ground truth.",
            "'LLM' throughout this report means MockLLMClient (LLM_MODE=mock) — no real "
            "provider exists in this project; these are not measurements of real-LLM behavior.",
        ],
    }
    return report


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
