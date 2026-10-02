"""Scores one live transaction with the trained fraud model
(`src/ml/train.py`, Phase 4) — the piece that was always missing from live
orchestration (`docs/project-status.md` § Phase 4/6/7/9/11/13 detail, each
honestly flagging that the model's score was never consulted at decision
time). `src/orchestration/live_case.py` is the only caller.

**Caching tradeoff, stated plainly, not hidden**: `src/ml/features.py::
build_features` is vectorized over the *whole* transactions table on
purpose — `merchant_fraud_rate_prior` is a dataset-wide expanding rate, not
a per-customer one, so it genuinely needs the full table in chronological
order. Recomputing that on every single live case request would make
`POST /cases` unacceptably slow (the Phase 4 velocity-feature rewrite alone
was measured at ~30s for 371k rows before it was vectorized; the full
feature build is the same order of cost). So this module keeps a
**module-level cache** — `(ModelArtifact, features_df)` — built once per
process on first use via the exact same loaders `src/ml/train.py` and
`evaluation/sample.py` already call, so there is exactly one feature
implementation in this project, not two that could silently drift apart.

The real, honestly-documented cost of that cache: a transaction ingested
*after* the process already built it won't be scoreable until the process
restarts (`clear_cache()` exists for tests, and as the manual escape hatch
if that ever matters locally). Acceptable for this prototype's static,
already-ingested sample (`docs/project-status.md` § Known limitations); a
real deployment would need a real feature store, not an in-process cache.
"""

from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.engine import Engine

from src.ml.dataset import load_complaints, load_customers, load_exchange_rates, load_transactions
from src.ml.features import build_features
from src.ml.model import MODEL_VERSION, ModelArtifact, predict_single

DEFAULT_MODEL_PATH = Path("data/models") / f"{MODEL_VERSION}.joblib"

_cache: tuple[ModelArtifact, pd.DataFrame] | None = None


def clear_cache() -> None:
    """Resets the module-level cache — used by tests, and as a manual
    escape hatch if newly-ingested data needs to be picked up without a
    full process restart."""
    global _cache
    _cache = None


def prime_cache(artifact: ModelArtifact, features_df: pd.DataFrame) -> None:
    """Lets a caller that already built the features table (`evaluation/
    sample.py`, which needs it for the Rules/Fraud-ML-only baselines
    anyway) hand it to this cache directly, instead of `score_transaction`
    rebuilding an identical one the first time it's called — the same
    whole-table feature build, paid for once either way, just not twice in
    the same process. `features_df` must have the shape `build_features`
    returns (a `transaction_id` column, not yet the index)."""
    global _cache
    _cache = (artifact, features_df.set_index("transaction_id"))


def _load_cache(engine: Engine, model_path: Path) -> tuple[ModelArtifact, pd.DataFrame] | None:
    global _cache
    if _cache is not None:
        return _cache
    try:
        artifact: ModelArtifact = joblib.load(model_path)
    except (FileNotFoundError, OSError, EOFError, ValueError):
        # Model never trained yet (a fresh clone before `uv run python -m
        # src.ml.train`), or a corrupt/incompatible artifact -- either way,
        # "no live score available" (model_degraded=True downstream), never
        # a crash (docs/architecture.md § 10: never fail open, but also
        # never let a missing optional dependency take down case creation).
        return None

    transactions = load_transactions(engine)
    customers = load_customers(engine)
    complaints = load_complaints(engine)
    exchange_rates = load_exchange_rates(engine)
    features_df = build_features(transactions, customers, complaints, exchange_rates).set_index(
        "transaction_id"
    )

    _cache = (artifact, features_df)
    return _cache


def score_transaction(
    engine: Engine, transaction_id: str, *, model_path: Path = DEFAULT_MODEL_PATH
) -> float | None:
    """Fraud probability for one transaction, or `None` if no live score is
    available (model artifact missing, or the transaction isn't in the
    currently-loaded/cached sample) — the caller (`live_case.py`) turns
    `None` into `CaseInput.model_degraded=True`, mirroring how an LLM
    failure becomes `llm_degraded=True` (Phase 9)."""
    cache = _load_cache(engine, model_path)
    if cache is None:
        return None
    artifact, features_df = cache
    if transaction_id not in features_df.index:
        return None
    # Every FEATURE_COLUMNS entry is numeric by construction (src/ml/features.py
    # builds them all as float columns) -- pandas-stubs' .at[] return type is
    # necessarily broader than that single real shape.
    features = {
        col: float(features_df.at[transaction_id, col])  # type: ignore[arg-type]
        for col in artifact.feature_columns
    }
    return predict_single(artifact, features)
