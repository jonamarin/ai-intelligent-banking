"""Main fraud/risk model: XGBoost (docs/model-evaluation.md § 4).

Every prediction this produces must carry model_name/model_version/
feature_version/timestamp (prompt.md § 54, docs/decision-policy.md § 9) —
ModelArtifact bundles that so a caller can't accidentally use the model
without also having its version metadata.
"""

import dataclasses
import datetime as dt

import numpy as np
import pandas as pd
import xgboost as xgb

MODEL_VERSION = "xgboost-v0.1.0"
FEATURE_VERSION = "features-v0.1.0"  # bump when src/ml/features.py's FEATURE_COLUMNS changes


@dataclasses.dataclass
class ModelArtifact:
    model: xgb.XGBClassifier
    model_name: str
    model_version: str
    feature_version: str
    trained_at: dt.datetime
    feature_columns: list[str]


def train_xgboost(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_val: pd.DataFrame,
    y_val: pd.Series,
    feature_columns: list[str],
) -> ModelArtifact:
    # Severe class imbalance (docs/project-status.md § Phase 4 detail: ~0.09%
    # fraud rate in the loaded sample) — scale_pos_weight compensates rather
    # than letting the model trivially predict "never fraud".
    n_pos = int(y_train.sum())
    n_neg = int(len(y_train) - n_pos)
    scale_pos_weight = (n_neg / n_pos) if n_pos else 1.0

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        early_stopping_rounds=20,
        random_state=42,
        missing=np.nan,
    )
    model.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)

    return ModelArtifact(
        model=model,
        model_name="xgboost",
        model_version=MODEL_VERSION,
        feature_version=FEATURE_VERSION,
        trained_at=dt.datetime.now(dt.UTC),
        feature_columns=feature_columns,
    )


def predict_proba(artifact: ModelArtifact, x: pd.DataFrame) -> np.ndarray:
    proba: np.ndarray = artifact.model.predict_proba(x[artifact.feature_columns])[:, 1]
    return proba
