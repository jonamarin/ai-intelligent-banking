"""Loads the ingested tables and computes the temporal train/validation/test
split (docs/model-evaluation.md § 2).

Split boundaries are computed from the data actually loaded, not hardcoded
calendar dates — this project's Phase 3 ingestion only loaded a bounded
recent-date sample (docs/project-status.md § Phase 3 detail), so hardcoding
e.g. "2025 Q1-Q3" as prompt.md's illustrative example does would silently
produce empty splits. Re-run `profile_date_range` if the loaded window changes.
"""

import dataclasses
import datetime as dt

import pandas as pd
from sqlalchemy.engine import Engine


@dataclasses.dataclass
class TemporalSplit:
    train_start: dt.date
    train_end: dt.date  # inclusive
    val_end: dt.date  # inclusive
    test_end: dt.date  # inclusive (== max date loaded)

    def label(self, date: pd.Series) -> pd.Series:
        d = pd.to_datetime(date).dt.date
        return pd.Series(
            [
                "train" if x <= self.train_end else "val" if x <= self.val_end else "test"
                for x in d
            ],
            index=date.index,
        )


def compute_split(
    min_date: dt.date,
    max_date: dt.date,
    *,
    train_frac: float = 0.667,
    val_frac: float = 0.167,
) -> TemporalSplit:
    """Earlier period -> train, middle -> validation, most recent -> test
    (docs/model-evaluation.md § 2) — proportional to whatever range is
    actually loaded, not a fixed calendar assumption."""
    total_days = (max_date - min_date).days
    train_end = min_date + dt.timedelta(days=round(total_days * train_frac))
    val_end = train_end + dt.timedelta(days=round(total_days * val_frac))
    if val_end >= max_date:
        val_end = max_date - dt.timedelta(days=1)
    return TemporalSplit(
        train_start=min_date, train_end=train_end, val_end=val_end, test_end=max_date
    )


def load_transactions(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT transaction_id, transaction_date, process_date, product_id, customer_id,
               transaction_type, transaction_category, amount, currency, amount_usd,
               channel, merchant_name, merchant_category, transaction_country,
               transaction_city, transaction_status, response_code, is_fraud,
               latitude, longitude
        FROM transactions
        ORDER BY transaction_date
        """,
        engine,
    )


def load_customers(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT customer_id, country, segment, registration_date FROM customers", engine
    )


def load_complaints(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT complaint_id, customer_id, creation_date, affected_product_id FROM complaints",
        engine,
    )


def load_exchange_rates(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT date, source_currency, target_currency, exchange_rate FROM daily_exchange_rates",
        engine,
    )


def load_digital_events(engine: Engine) -> pd.DataFrame:
    """`customer_id IS NOT NULL` -- a ~24% null rate is a real, documented
    data-quality characteristic of this table (`src/ingestion/README.md`),
    and an event with no customer can never be matched to that customer's
    transactions anyway (`src/ml/features.py`'s device/IP-novelty
    features), so filtering here avoids loading rows into pandas that
    `build_features` could never use."""
    return pd.read_sql(
        """
        SELECT event_id, event_date, customer_id, session_id, platform, browser,
               ip_address, ip_country, ip_city
        FROM digital_events
        WHERE customer_id IS NOT NULL
        """,
        engine,
    )


def diagnose_fraud_score_separation(engine: Engine) -> dict:
    """Diagnostic only — NEVER a feature (docs/data-lineage.md § 5).

    Reports whether the dataset's own (excluded) fraud_score field actually
    separates is_fraud classes, so a near-random model evaluation
    (docs/project-status.md § Phase 4 detail) can be read as "the behavioral
    features available don't carry the signal" rather than "no signal exists
    in this dataset at all" — those are different, both important, findings.
    """
    df = pd.read_sql(
        "SELECT is_fraud, fraud_score FROM transactions WHERE fraud_score IS NOT NULL", engine
    )
    summary = df.groupby("is_fraud")["fraud_score"].agg(["count", "mean", "std", "min", "max"])
    return {
        str(k): {stat: float(v) for stat, v in row.items()}
        for k, row in summary.to_dict(orient="index").items()
    }
