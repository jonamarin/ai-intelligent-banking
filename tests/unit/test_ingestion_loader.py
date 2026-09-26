"""Regression tests for src/ingestion/loader.py's NA-handling.

pandas >= 3.0 gives plain string columns a dedicated `str` dtype whose
missing-value marker is `float('nan')`, not `None` — a real, observed
behavior change from pandas < 3.0 that silently broke this loader's nullable
foreign-key handling (a `v is None` check saw 0 matches on a column that was
86/217 null). These tests pin the fix (`pd.isna`-based, never `is None`) so
a future pandas upgrade or refactor can't quietly reintroduce it.
"""

import pandas as pd

from src.ingestion.loader import _coerce_types, _none_if_na


def test_coerced_string_column_nulls_are_detected_via_isna() -> None:
    df = pd.DataFrame({"affected_product_id": ["PRD-1", None, float("nan"), "PRD-2"]})
    coerced = _coerce_types(
        df, bool_columns=[], date_columns=[], datetime_columns=[], int_columns=[], json_columns=[]
    )
    # The regression: on pandas >= 3.0 these come back as `str`-dtype with a
    # NaN marker, not `None` — `pd.isna` must still find exactly 2 nulls.
    assert pd.isna(coerced["affected_product_id"]).sum() == 2


def test_none_if_na_normalizes_both_none_and_nan_to_none() -> None:
    assert _none_if_na(None) is None
    assert _none_if_na(float("nan")) is None
    assert _none_if_na("PRD-1") == "PRD-1"


def test_none_if_na_leaves_containers_alone() -> None:
    # pd.isna on a dict/list raises/misbehaves — must never reach it for these.
    assert _none_if_na({"a": 1}) == {"a": 1}
    assert _none_if_na([1, 2, 3]) == [1, 2, 3]
