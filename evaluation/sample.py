"""Builds the ONE held-out sample every approach in `baselines.py` is
compared against (`docs/evaluation-plan.md` § 10: "Compare, on the SAME
held-out workload"). Drawn from Phase 4's own temporal **test** split
(`data/reports/fraud_model_evaluation.json`: 2026-06-03 to 2026-06-18),
further restricted to the `digital_events` window (2026-06-11 to
2026-06-18) so the Evidence Engine's device-history signal isn't trivially
`Unknown` for every case, and bounded in size because building one evidence
graph costs several DB queries each — not something to do for tens of
thousands of rows in an interactive evaluation run.

Class imbalance is severe (`docs/project-status.md` § Phase 4 detail: ~0.09%
fraud rate) — a uniform random sample of this size would very likely
contain zero fraud cases and make every comparison metric meaningless. This
sample deliberately includes **every** fraud transaction in the window plus
a random sample of legitimate ones — an intentional, stated oversampling of
the rare positive class for evaluation purposes only, never presented as
the dataset's natural prevalence (`docs/evaluation-plan.md` § 1).
"""

import dataclasses
import random
from typing import Any

import joblib
from sqlalchemy.engine import Engine

from src.evidence.graph import build_evidence_graph
from src.ml.dataset import (
    load_complaints,
    load_customers,
    load_digital_events,
    load_exchange_rates,
    load_transactions,
)
from src.ml.features import FEATURE_COLUMNS, build_features
from src.ml.score import DEFAULT_MODEL_PATH, prime_cache
from src.orchestration.case import CaseInput
from src.orchestration.live_case import case_input_from_graph

DIGITAL_EVENTS_WINDOW_START = "2026-06-11"
DIGITAL_EVENTS_WINDOW_END = "2026-06-18"
DEFAULT_LEGIT_SAMPLE_SIZE = 120
RANDOM_SEED = 42


@dataclasses.dataclass
class EvalCase:
    transaction_id: str
    customer_id: str
    is_fraud: bool
    country: str | None
    segment: str | None
    features: dict[str, float]  # FEATURE_COLUMNS -> value, for Rules/ML baselines
    case_input: CaseInput  # real evidence graph, for LLM-only/Hybrid


def build_eval_sample(
    engine: Engine,
    *,
    legit_sample_size: int = DEFAULT_LEGIT_SAMPLE_SIZE,
    seed: int = RANDOM_SEED,
) -> list[EvalCase]:
    # Feature engineering needs each customer's full prior history
    # (src/ml/features.py) — computed over the whole loaded sample, exactly
    # as Phase 4 did, then filtered down to the selected transaction_ids so
    # the "Fraud ML" baseline sees the identical feature values training
    # produced (no re-derivation, no drift from Phase 4's own numbers).
    transactions = load_transactions(engine)
    customers = load_customers(engine)
    complaints = load_complaints(engine)
    exchange_rates = load_exchange_rates(engine)
    digital_events = load_digital_events(engine)
    features_df = build_features(
        transactions, customers, complaints, exchange_rates, digital_events
    )

    # Phase 15 (src/ml/score.py): prime the live-scoring cache with the
    # features this function already built, so `case_input_from_graph`
    # below (which now calls `score_transaction` internally) reuses it
    # instead of reloading/recomputing the whole-table feature build a
    # second time — the exact ~30s-at-this-scale cost this cache exists to
    # avoid paying more than once per process (src/ml/score.py's own
    # docstring). The artifact is required here, not optional: the
    # "Fraud ML only" baseline below already depends on it existing
    # (evaluation/baselines.py's own fail-loudly test,
    # tests/unit/test_evaluation.py), so a missing artifact should fail
    # this run loudly too, not degrade the Hybrid row silently.
    artifact = joblib.load(DEFAULT_MODEL_PATH)
    prime_cache(artifact, features_df)

    in_window = transactions[
        (transactions["transaction_date"] >= DIGITAL_EVENTS_WINDOW_START)
        & (transactions["transaction_date"] <= DIGITAL_EVENTS_WINDOW_END + " 23:59:59")
    ]
    fraud_ids = in_window.loc[in_window["is_fraud"], "transaction_id"].tolist()
    legit_ids_all = in_window.loc[~in_window["is_fraud"], "transaction_id"].tolist()
    rng = random.Random(seed)
    legit_ids = rng.sample(legit_ids_all, min(legit_sample_size, len(legit_ids_all)))
    selected_ids = [*fraud_ids, *legit_ids]

    features_by_id = features_df.set_index("transaction_id")
    customers_by_id = customers.set_index("customer_id")

    cases: list[EvalCase] = []
    for transaction_id in selected_ids:
        row = features_by_id.loc[transaction_id]
        customer_id = str(row["customer_id"])
        customer_row = (
            customers_by_id.loc[customer_id] if customer_id in customers_by_id.index else None
        )

        graph = build_evidence_graph(engine, transaction_id)
        case_input = case_input_from_graph(engine, graph)

        cases.append(
            EvalCase(
                transaction_id=transaction_id,
                customer_id=customer_id,
                is_fraud=bool(row["is_fraud"]),
                country=str(customer_row["country"]) if customer_row is not None else None,
                segment=str(customer_row["segment"]) if customer_row is not None else None,
                features={col: float(row[col]) for col in FEATURE_COLUMNS},
                case_input=case_input,
            )
        )
    return cases


def sample_summary(cases: list[EvalCase]) -> dict[str, Any]:
    return {
        "sample_size": len(cases),
        "fraud_count": sum(1 for c in cases if c.is_fraud),
        "legit_count": sum(1 for c in cases if not c.is_fraud),
        "window": {"start": DIGITAL_EVENTS_WINDOW_START, "end": DIGITAL_EVENTS_WINDOW_END},
        "note": "Every in-window fraud transaction plus a random sample of legitimate ones — "
        "an intentional oversample of the rare positive class for evaluation, not the "
        "dataset's natural ~0.09% prevalence (docs/evaluation-plan.md § 1).",
    }
