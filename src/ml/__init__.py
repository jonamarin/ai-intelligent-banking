"""Fraud/risk ML: baseline + main model, feature engineering, evaluation.

docs/architecture.md § 3: this package produces a calibrated, versioned
*prediction* — never a decision. Owns docs/model-evaluation.md §§ 2-7.
Entry point: `uv run python -m src.ml.train` (see train.py).

Not part of the src/ subpackages enumerated in the original master prompt's
sketch (which used `models/` for what this project calls domain models,
src/models/) — added as a justified, documented deviation: ML training code
needs its own home distinct from the SQLAlchemy ORM layer.
"""
