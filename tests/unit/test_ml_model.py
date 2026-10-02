"""Tests for src/ml/model.py — offline, no DB. `train_xgboost`/`predict_proba`
are already exercised end-to-end by `uv run python -m src.ml.train` against
real data; this file covers `predict_single` (Phase 15,
src/ml/score.py's only caller) against a tiny, fast, fully-offline fitted
model.
"""

import pandas as pd

from src.ml.model import predict_single, train_xgboost

_FEATURE_COLUMNS = ["amount_deviation", "country_deviation"]


def _tiny_dataset() -> tuple[pd.DataFrame, pd.Series]:
    x = pd.DataFrame(
        {
            "amount_deviation": [0.1, 0.2, 5.0, 6.0, 0.0, 0.3, 5.5, 4.8],
            "country_deviation": [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
        }
    )
    y = pd.Series([0, 0, 1, 1, 0, 0, 1, 1])
    return x, y


def test_predict_single_returns_a_probability_in_range() -> None:
    x, y = _tiny_dataset()
    artifact = train_xgboost(x, y, x, y, _FEATURE_COLUMNS)
    score = predict_single(artifact, {"amount_deviation": 5.2, "country_deviation": 1.0})
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_predict_single_matches_predict_proba_for_the_same_row() -> None:
    """predict_single is a convenience wrapper, not a second
    implementation — it must agree exactly with the batch path."""
    x, y = _tiny_dataset()
    artifact = train_xgboost(x, y, x, y, _FEATURE_COLUMNS)
    features = {"amount_deviation": 5.2, "country_deviation": 1.0}

    from src.ml.model import predict_proba

    batch_score = float(predict_proba(artifact, pd.DataFrame([features]))[0])
    assert predict_single(artifact, features) == batch_score


def test_predict_single_ignores_extra_dict_keys_not_in_feature_columns() -> None:
    """src/ml/score.py builds `features` from `artifact.feature_columns`
    directly, so this shouldn't come up in practice -- but predict_single
    must not silently use the wrong columns if a caller passes extras."""
    x, y = _tiny_dataset()
    artifact = train_xgboost(x, y, x, y, _FEATURE_COLUMNS)
    features = {
        "amount_deviation": 5.2,
        "country_deviation": 1.0,
        "some_unrelated_column": 999.0,
    }
    score = predict_single(artifact, features)
    assert 0.0 <= score <= 1.0
