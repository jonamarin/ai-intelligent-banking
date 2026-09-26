"""Leakage-safety and correctness tests for src/ml/features.py.

docs/implementation-roadmap.md Phase 4 requires leakage checks as an
automated test, not just a design decision documented in prose — these pin
the two real bugs found during Phase 4 verification (currency-scale mixing,
and the "0" vs "00" response-code comparison) so they can't regress.
"""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.ml.features import FEATURE_COLUMNS, build_features


def _customers() -> pd.DataFrame:
    return pd.DataFrame(
        {"customer_id": ["C1", "C2"], "country": ["Mexico", "Colombia"]}
    )


def _no_complaints() -> pd.DataFrame:
    return pd.DataFrame(columns=["complaint_id", "customer_id", "creation_date"])


def _no_extra_rates() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["date", "source_currency", "target_currency", "exchange_rate"]
    )


def test_label_columns_are_never_features() -> None:
    assert "is_fraud" not in FEATURE_COLUMNS
    assert "fraud_score" not in FEATURE_COLUMNS


def test_first_transaction_has_no_prior_history() -> None:
    txns = pd.DataFrame(
        {
            "transaction_id": ["T1"],
            "transaction_date": [dt.datetime(2026, 1, 1, 10, 0)],
            "process_date": [dt.date(2026, 1, 1)],
            "customer_id": ["C1"],
            "amount": [100.0],
            "amount_usd": [100.0],
            "currency": ["USD"],
            "channel": ["POS"],
            "merchant_name": ["M1"],
            "merchant_category": ["Food"],
            "transaction_country": ["Mexico"],
            "transaction_city": ["CDMX"],
            "transaction_status": ["Approved"],
            "response_code": ["0"],
            "is_fraud": [False],
            "transaction_type": ["Purchase"],
            "latitude": [None],
            "longitude": [None],
        }
    )
    feats = build_features(txns, _customers(), _no_complaints(), _no_extra_rates())
    row = feats.iloc[0]
    assert row["cust_txn_count_prior"] == 0
    assert row["cust_txn_count_last_24h"] == 0
    assert np.isnan(row["amount_deviation"]) or row["amount_deviation"] == 0
    assert np.isnan(row["merchant_fraud_rate_prior"])


def test_prior_stats_never_use_the_current_or_future_row() -> None:
    """Three transactions for one customer, strictly increasing in time —
    the 2nd's prior count/mean must reflect only the 1st, and the 1st's
    prior stats must never see the 2nd or 3rd (the actual leakage bug this
    guards: any accidental non-shifted expanding window)."""
    txns = pd.DataFrame(
        {
            "transaction_id": ["T1", "T2", "T3"],
            "transaction_date": [
                dt.datetime(2026, 1, 1, 10, 0),
                dt.datetime(2026, 1, 2, 10, 0),
                dt.datetime(2026, 1, 3, 10, 0),
            ],
            "process_date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 3)],
            "customer_id": ["C1", "C1", "C1"],
            "amount": [100.0, 200.0, 9999.0],  # T3 is a huge outlier
            "amount_usd": [100.0, 200.0, 9999.0],
            "currency": ["USD", "USD", "USD"],
            "channel": ["POS", "POS", "POS"],
            "merchant_name": ["M1", "M1", "M1"],
            "merchant_category": ["Food", "Food", "Food"],
            "transaction_country": ["Mexico", "Mexico", "Mexico"],
            "transaction_city": ["CDMX", "CDMX", "CDMX"],
            "transaction_status": ["Approved", "Approved", "Approved"],
            "response_code": ["0", "0", "0"],
            "is_fraud": [False, False, True],
            "transaction_type": ["Purchase", "Purchase", "Purchase"],
            "latitude": [None, None, None],
            "longitude": [None, None, None],
        }
    )
    feats = build_features(txns, _customers(), _no_complaints(), _no_extra_rates())
    feats = feats.set_index("transaction_id")

    # T2's prior count is 1 (only T1 came before it) — never 2.
    assert feats.loc["T2", "cust_txn_count_prior"] == 1
    assert feats.loc["T3", "cust_txn_count_prior"] == 2

    # T1's amount_deviation must not be influenced by T3's huge amount —
    # with zero prior history it's undefined, not some function of the future.
    assert np.isnan(feats.loc["T1", "amount_deviation"])


def test_response_code_zero_is_treated_as_success() -> None:
    """Regression test: the dataset's success code is the string "0", not
    "00" — comparing against "00" silently flagged ~95% of transactions as
    auth_failed in an earlier version of this module."""
    txns = pd.DataFrame(
        {
            "transaction_id": ["T1"],
            "transaction_date": [dt.datetime(2026, 1, 1, 10, 0)],
            "process_date": [dt.date(2026, 1, 1)],
            "customer_id": ["C1"],
            "amount": [100.0],
            "amount_usd": [100.0],
            "currency": ["USD"],
            "channel": ["POS"],
            "merchant_name": ["M1"],
            "merchant_category": ["Food"],
            "transaction_country": ["Mexico"],
            "transaction_city": ["CDMX"],
            "transaction_status": ["Approved"],
            "response_code": ["0"],
            "is_fraud": [False],
            "transaction_type": ["Purchase"],
            "latitude": [None],
            "longitude": [None],
        }
    )
    feats = build_features(txns, _customers(), _no_complaints(), _no_extra_rates())
    assert feats.iloc[0]["auth_failed"] == 0.0


def test_non_usd_amount_is_converted_not_used_raw() -> None:
    """Regression test: a raw COP amount (millions) must never be compared
    directly against a raw USD amount (hundreds) — an earlier version of
    this module fell back to the unconverted `amount` column, producing
    amount_deviation values up to ~4e13."""
    txns = pd.DataFrame(
        {
            "transaction_id": ["T1"],
            "transaction_date": [dt.datetime(2026, 1, 1, 10, 0)],
            "process_date": [dt.date(2026, 1, 1)],
            "customer_id": ["C1"],
            "amount": [10_000_000.0],  # 10M COP
            "amount_usd": [None],
            "currency": ["COP"],
            "channel": ["POS"],
            "merchant_name": ["M1"],
            "merchant_category": ["Food"],
            "transaction_country": ["Colombia"],
            "transaction_city": ["Bogota"],
            "transaction_status": ["Approved"],
            "response_code": ["0"],
            "is_fraud": [False],
            "transaction_type": ["Purchase"],
            "latitude": [None],
            "longitude": [None],
        }
    )
    rates = pd.DataFrame(
        {
            "date": [dt.date(2026, 1, 1)],
            "source_currency": ["COP"],
            "target_currency": ["USD"],
            "exchange_rate": [0.00025],  # 10M COP -> $2,500
        }
    )
    feats = build_features(txns, _customers(), _no_complaints(), rates)
    assert feats.iloc[0]["amount_usd"] == pytest.approx(2500.0)
