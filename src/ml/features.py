"""Leakage-safe feature engineering (docs/model-evaluation.md § 3, § 4).

Every rolling/historical feature here is computed strictly from data at or
before the timestamp it's attached to (a cumulative/expanding statistic minus
the current row's own contribution, or an explicit `< current_timestamp`
comparison) — a transaction never sees its own future, another customer's
future, or (for the merchant-risk feature) the dataset's future.
`transactions.fraud_score` and `is_fraud` are never used as a *feature*
(`is_fraud` is the label — see train.py) per docs/data-lineage.md § 5.

All per-customer aggregates are computed with vectorized groupby
cumsum/cumcount/shift — not `.transform(lambda ...)` with an `.expanding()`
call inside, which is Python-level-call-per-group and was measured at ~10
minutes for 371k rows / 116k customers before this rewrite. The vectorized
version computes the same statistics in seconds.

Device/IP-novelty and true geographic-distance features are NOT_IMPLEMENTED
here — they need the Device entity (docs/domain-model.md § Device), which is
derived from digital_events (not loaded in this ingestion run; Phase 5 owns
that derivation properly). Listed explicitly in FEATURE_COLUMNS with a note
rather than silently omitted.
"""

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "amount_usd",
    "amount_deviation",
    "cust_txn_count_prior",
    "cust_txn_count_last_24h",
    "cust_txn_count_last_7d",
    "country_deviation",
    "hour_of_day",
    "hour_deviation",
    "merchant_fraud_rate_prior",
    "cust_complaint_count_prior",
    "card_present",
    "auth_failed",
    "has_geo",
    "channel_encoded",
    "transaction_type_encoded",
]

# Explicitly not implemented — documented, not silently dropped. See module
# docstring for why (needs Phase 5's Device derivation from digital_events).
NOT_IMPLEMENTED_FEATURES = ["device_novelty", "ip_novelty", "geographic_distance_km"]

_CARD_PRESENT_CHANNELS = {"POS", "ATM", "Branch"}
_SUCCESS_RESPONSE_CODES = {"0", "00"}


def _cumulative_prior_mean_std(
    df: pd.DataFrame, group_col: str, value_col: str
) -> tuple[pd.Series, pd.Series]:
    """Strictly-prior expanding mean/std of `value_col` within `group_col`,
    computed via cumsum/cumsum-of-squares (vectorized — no per-group Python
    calls) rather than `.expanding()`, for tractable runtime at this scale.
    """
    sq_col = df[value_col] ** 2
    cum_n_incl = df.groupby(group_col).cumcount() + 1
    cum_sum_incl = df.groupby(group_col)[value_col].cumsum()
    cum_sq_incl = sq_col.groupby(df[group_col]).cumsum()

    n_prior = cum_n_incl - 1
    sum_prior = cum_sum_incl - df[value_col]
    sq_prior = cum_sq_incl - sq_col

    n_prior_safe = n_prior.astype(float).where(n_prior != 0, np.nan)
    mean_prior = sum_prior / n_prior_safe
    mean_sq_prior = sq_prior / n_prior_safe
    var_prior = (mean_sq_prior - mean_prior**2).clip(lower=0)
    std_prior = pd.Series(np.sqrt(var_prior.to_numpy()), index=df.index)
    return mean_prior, std_prior


def _convert_to_usd(transactions: pd.DataFrame, exchange_rates: pd.DataFrame) -> pd.Series:
    """Uses transactions.amount_usd where present; otherwise converts
    transactions.amount via daily_exchange_rates (source_currency -> USD on
    process_date). Never falls back to the raw, currency-unconverted amount
    — this dataset's currencies (ARS/COP/MXN/USD) differ by orders of
    magnitude (observed: ARS avg ~586k, COP avg ~6.7M, USD avg ~1.7k), so
    mixing raw amounts across currencies would make `amount_deviation`
    meaningless (a bug caught during verification — see
    docs/project-status.md § Phase 4 detail)."""
    df = transactions[["transaction_id", "amount", "currency", "process_date", "amount_usd"]]
    usd_rates = exchange_rates[exchange_rates["target_currency"] == "USD"][
        ["source_currency", "date", "exchange_rate"]
    ].rename(columns={"source_currency": "currency", "date": "process_date"})

    merged = df.merge(usd_rates, on=["currency", "process_date"], how="left")
    computed = merged["amount"].astype(float) * merged["exchange_rate"].astype(float)
    is_usd = merged["currency"] == "USD"
    computed = computed.where(~is_usd, merged["amount"].astype(float))
    amount_usd_given = pd.to_numeric(merged["amount_usd"], errors="coerce")
    result = amount_usd_given.where(amount_usd_given.notna(), computed)
    return pd.Series(result.to_numpy(dtype=float), index=transactions.index, name="amount_usd")


def build_features(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
    complaints: pd.DataFrame,
    exchange_rates: pd.DataFrame,
) -> pd.DataFrame:
    """Returns one row per transaction_id with FEATURE_COLUMNS plus
    transaction_id, customer_id, transaction_date, and the label is_fraud —
    ready to be temporally split (dataset.py) and fed to a model (model.py).
    """
    df = transactions.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["process_date"] = pd.to_datetime(df["process_date"]).dt.date
    df = df.sort_values(["customer_id", "transaction_date", "transaction_id"]).reset_index(
        drop=True
    )

    df["amount_usd"] = _convert_to_usd(df, exchange_rates)

    mean_prior, std_prior = _cumulative_prior_mean_std(df, "customer_id", "amount_usd")
    # Guard against a near-zero std amplifying a tiny difference into a huge
    # z-score for customers with very little prior history (e.g. exactly one
    # prior transaction) — floor the denominator at 1% of that customer's own
    # prior mean (or $1, whichever is larger) rather than a fixed epsilon.
    denom_candidates = pd.concat(
        [std_prior, mean_prior.abs() * 0.01, pd.Series(1.0, index=df.index)], axis=1
    )
    denom = denom_candidates.max(axis=1)
    df["amount_deviation"] = (df["amount_usd"] - mean_prior) / denom

    df["cust_txn_count_prior"] = df.groupby("customer_id").cumcount()

    # Time-windowed velocity: native grouped .rolling(), not .transform(lambda) —
    # the same statistic, computed via pandas' internal grouped-rolling path
    # instead of one Python callable invocation per of 116k customer groups.
    ts_indexed = df.set_index("transaction_date")
    for window, col in (("24h", "cust_txn_count_last_24h"), ("7D", "cust_txn_count_last_7d")):
        counts_incl_self = (
            ts_indexed.groupby("customer_id")["transaction_id"]
            .rolling(window)
            .count()
            .reset_index(level=0, drop=True)
        )
        df[col] = counts_incl_self.to_numpy() - 1  # exclude the current transaction itself

    df = df.merge(customers[["customer_id", "country"]], on="customer_id", how="left")
    df["country_deviation"] = (df["transaction_country"] != df["country"]).astype(float)
    df["country_deviation"] = df["country_deviation"].where(df["country"].notna())

    df["hour_of_day"] = df["transaction_date"].dt.hour.astype(float)
    hour_mean_prior, _ = _cumulative_prior_mean_std(df, "customer_id", "hour_of_day")
    df["hour_deviation"] = (df["hour_of_day"] - hour_mean_prior).abs()

    # Merchant risk: dataset-wide expanding fraud rate per merchant_category,
    # strictly prior in GLOBAL time order (not per-customer) — avoids leaking
    # any split's labels into another's features, without needing the split
    # to be computed first. Few distinct categories, so a per-group
    # transform is not a performance concern here.
    df = df.sort_values(["transaction_date", "transaction_id"]).reset_index(drop=True)
    df["merchant_fraud_rate_prior"] = df.groupby("merchant_category")["is_fraud"].transform(
        lambda s: s.astype(float).expanding().mean().shift(1)
    )

    df["cust_complaint_count_prior"] = _prior_complaint_counts(df, complaints)

    df["card_present"] = df["channel"].isin(_CARD_PRESENT_CHANNELS).astype(float)
    response_ok = df["response_code"].fillna("0").isin(_SUCCESS_RESPONSE_CODES)
    df["auth_failed"] = ((df["transaction_status"] == "Declined") | ~response_ok).astype(float)
    df["has_geo"] = df["latitude"].notna().astype(float)
    df["channel_encoded"] = df["channel"].astype("category").cat.codes.astype(float)
    df["transaction_type_encoded"] = df["transaction_type"].astype("category").cat.codes.astype(
        float
    )

    keep = ["transaction_id", "customer_id", "transaction_date", "is_fraud", *FEATURE_COLUMNS]
    return df[keep].sort_values("transaction_date").reset_index(drop=True)


def _prior_complaint_counts(transactions: pd.DataFrame, complaints: pd.DataFrame) -> pd.Series:
    if complaints.empty:
        return pd.Series(0.0, index=transactions.index)

    txn_events = transactions[["customer_id", "transaction_date", "transaction_id"]].copy()
    txn_events["event_date"] = txn_events["transaction_date"]
    txn_events["is_complaint"] = 0

    complaint_events = complaints[["customer_id", "creation_date"]].copy()
    complaint_events["event_date"] = pd.to_datetime(complaint_events["creation_date"])
    complaint_events["is_complaint"] = 1
    complaint_events["transaction_id"] = np.nan

    combined = pd.concat(
        [
            txn_events[["customer_id", "event_date", "is_complaint", "transaction_id"]],
            complaint_events[["customer_id", "event_date", "is_complaint", "transaction_id"]],
        ],
        ignore_index=True,
    )
    combined = combined.sort_values(["customer_id", "event_date"])
    combined["cust_complaint_count_prior"] = combined.groupby("customer_id")[
        "is_complaint"
    ].cumsum()

    result = combined[combined["transaction_id"].notna()].set_index("transaction_id")[
        "cust_complaint_count_prior"
    ]
    # cumsum includes the current row's own is_complaint (0 for a
    # transaction row), so this already excludes the transaction itself —
    # but a complaint at the exact same instant would double count; that's
    # an acceptable, documented edge case at datetime precision.
    return transactions["transaction_id"].map(result).astype(float)
