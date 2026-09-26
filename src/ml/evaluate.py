"""Evaluation metrics (docs/evaluation-plan.md § 2, § 8).

Every number this module produces must be labeled per docs/evaluation-plan.md
§ 1 when reported — `MEASURED` here means "computed from an actual held-out
split of the currently-loaded sample," not a claim about the full dataset or
a production system. Business-cost metrics (docs/evaluation-plan.md § 3) are
deliberately NOT computed here — no business-approved cost coefficients
exist in this project; fabricating a dollar figure would violate
CLAUDE.md § 7. Report `not available` for those, don't estimate one.
"""

import dataclasses

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclasses.dataclass
class ClassificationMetrics:
    sample_size: int
    positive_count: int
    threshold: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    false_positive_rate: float
    false_negative_rate: float
    confusion_matrix: list[list[int]]
    calibration_bins: list[dict[str, float]]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def evaluate(
    y_true: np.ndarray, y_pred_proba: np.ndarray, *, threshold: float = 0.5
) -> ClassificationMetrics:
    y_pred = (y_pred_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    fpr = fp / (fp + tn) if (fp + tn) else float("nan")
    fnr = fn / (fn + tp) if (fn + tp) else float("nan")

    try:
        roc_auc = float(roc_auc_score(y_true, y_pred_proba))
    except ValueError:
        roc_auc = float("nan")  # only one class present in y_true

    calibration_bins: list[dict[str, float]] = []
    try:
        prob_true, prob_pred = calibration_curve(
            y_true, y_pred_proba, n_bins=10, strategy="quantile"
        )
        calibration_bins = [
            {"predicted": float(p), "observed": float(o)}
            for p, o in zip(prob_pred, prob_true, strict=True)
        ]
    except ValueError:
        pass  # too few positive examples to bin meaningfully — leave empty, not fabricated

    return ClassificationMetrics(
        sample_size=len(y_true),
        positive_count=int(y_true.sum()),
        threshold=threshold,
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        roc_auc=roc_auc,
        pr_auc=float(average_precision_score(y_true, y_pred_proba)),
        false_positive_rate=float(fpr),
        false_negative_rate=float(fnr),
        confusion_matrix=[[int(tn), int(fp)], [int(fn), int(tp)]],
        calibration_bins=calibration_bins,
    )
