"""SHAP explainability (docs/model-evaluation.md § 6) — feeds the
analyst-facing explanation's "top contributing features" requirement
(prompt.md § 22; docs/architecture.md § 3 AI responsibilities). Global
feature importance only in this phase; per-case SHAP explanation is wired
into the analyst UI in Phase 10.
"""

import pandas as pd
import shap
import xgboost as xgb


def global_feature_importance(
    model: xgb.XGBClassifier, x_sample: pd.DataFrame, feature_columns: list[str]
) -> list[dict[str, str | float]]:
    """Mean absolute SHAP value per feature over `x_sample`, sorted
    descending. `x_sample` should be a held-out (e.g. validation) slice —
    never the training data the model memorized."""
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(x_sample[feature_columns])
    mean_abs = pd.Series(abs(shap_values).mean(axis=0), index=feature_columns)
    ranked = mean_abs.sort_values(ascending=False)
    return [
        {"feature": str(name), "mean_abs_shap": float(value)} for name, value in ranked.items()
    ]
