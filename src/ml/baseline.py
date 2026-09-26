"""Baseline model (docs/model-evaluation.md § 4, § 12) — the floor the main
model must beat before any claim of the hybrid/XGBoost approach being
"better" is credible (docs/evaluation-plan.md § 10)."""

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def train_baseline(x_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "classify",
                LogisticRegression(
                    max_iter=1000, class_weight="balanced", random_state=42
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    return pipeline


def predict_proba(pipeline: Pipeline, x: pd.DataFrame) -> np.ndarray:
    proba: np.ndarray = pipeline.predict_proba(x)[:, 1]
    return proba
