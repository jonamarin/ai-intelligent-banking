"""Generic CSV -> PostgreSQL loader used by every table in run.py.

Handles the dataset's documented data-quality characteristics explicitly
(docs/data-lineage.md § 2) rather than assuming clean input:

- Duplicate rows (on the primary key, or on any other unique constraint —
  the ~2% duplicate rate shows up on secondary unique columns too, e.g.
  products.product_number) are treated as skippable, not fatal.
- Rows with a foreign key pointing at a customer/product/interaction that
  was never loaded (the documented "small percentage of orphaned records")
  are skipped and counted rather than left to crash the insert.
- Rows with a NULL in a column our schema declares NOT NULL — which really
  happens in this dataset even for fields the data dictionary calls
  mandatory — either fall back to the column's declared Python-side
  default (if any) or are dropped and counted, never silently coerced to a
  wrong value or allowed to crash the whole batch.

Uses the actual declarative model classes (not raw reflected tables) so that
`mapped_column(default=...)` is available to decide the above.
"""

import json
import time
from pathlib import Path
from typing import Any, cast

import pandas as pd
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase

from src.ingestion.quality import TableQualityReport

# Postgres caps a single query at 65535 bound parameters; the widest table
# here has ~30 columns, so 1000 rows/batch (~30,000 params) stays safely
# under that regardless of which table is being loaded.
BATCH_SIZE = 1_000


class ForeignKeyCheck:
    """One FK column to validate against another table's already-loaded IDs.

    `nullable` must match the model column — a nullable FK's null values are
    always allowed through untouched; only non-null values are checked.
    """

    def __init__(
        self,
        column: str,
        referenced_model: type[DeclarativeBase],
        referenced_column: str,
        *,
        nullable: bool,
    ):
        self.column = column
        self.referenced_model = referenced_model
        self.referenced_column = referenced_column
        self.nullable = nullable


def _read_csvs(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(p, encoding="utf-8-sig", low_memory=False) for p in paths]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _parse_json_or_none(value: Any) -> Any:
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def _coerce_types(
    df: pd.DataFrame,
    *,
    bool_columns: list[str],
    date_columns: list[str],
    datetime_columns: list[str],
    int_columns: list[str],
    json_columns: list[str],
) -> pd.DataFrame:
    for col in bool_columns:
        if col in df.columns:
            df[col] = df[col].map({True: True, False: False, "True": True, "False": False})
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    for col in datetime_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in int_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in json_columns:
        if col in df.columns:
            df[col] = df[col].map(_parse_json_or_none)
    return df


def _none_if_na(value: Any) -> Any:
    """Normalize a missing value to Python `None`.

    pandas >= 3.0 gives plain string columns its own `str` dtype whose
    missing marker is `float('nan')`, not `None` — a `.where(notnull, None)`
    pass over the whole frame does *not* reliably convert it (unlike on
    pandas < 3.0, where object-dtype columns did). Checking `value is None`
    anywhere in this module is therefore wrong on its own; every missing-value
    check must go through `pd.isna` (here, once, at record-build time) so
    everything downstream — the NOT NULL/default logic, and the actual
    psycopg bind values — sees a real `None`, never a stray NaN.
    """
    if isinstance(value, dict | list):
        return value  # pd.isna on a container raises/misbehaves; never NA here
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return value


def _apply_not_null_defaults_or_drop(
    records: list[dict[str, Any]], table: Table
) -> tuple[list[dict[str, Any]], int]:
    """For each NOT NULL, non-primary-key column: if a row's value is None
    and the column has a declared Python-side default, drop the key so the
    Core insert applies that default. If the column has no default, drop the
    whole row (counted, not silently inserted with a wrong value)."""
    required_no_default = [
        c.name
        for c in table.columns
        if not c.nullable and not c.primary_key and c.default is None and c.server_default is None
    ]
    required_with_default = [
        c.name
        for c in table.columns
        if not c.nullable
        and not c.primary_key
        and (c.default is not None or c.server_default is not None)
    ]

    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in records:
        if any(row.get(col) is None for col in required_no_default):
            dropped += 1
            continue
        for col in required_with_default:
            if row.get(col) is None:
                del row[col]
        kept.append(row)
    return kept, dropped


def load_table(
    conn: Connection,
    *,
    model: type[DeclarativeBase],
    csv_paths: list[Path],
    pk_columns: list[str],
    bool_columns: list[str] | None = None,
    date_columns: list[str] | None = None,
    datetime_columns: list[str] | None = None,
    int_columns: list[str] | None = None,
    json_columns: list[str] | None = None,
    fk_checks: list[ForeignKeyCheck] | None = None,
) -> TableQualityReport:
    table = cast(Table, model.__table__)
    table_name = table.name
    start = time.monotonic()
    df = _read_csvs(csv_paths)
    source_row_count = len(df)

    if source_row_count == 0:
        return TableQualityReport(
            table_name=table_name,
            source_row_count=0,
            duplicates_removed=0,
            orphaned_fk_rows_skipped={},
            null_rate_by_column={},
            rows_loaded=0,
            elapsed_seconds=time.monotonic() - start,
        )

    before_dedup = len(df)
    df = df.drop_duplicates(subset=pk_columns, keep="first")
    duplicates_removed = before_dedup - len(df)

    df = _coerce_types(
        df,
        bool_columns=bool_columns or [],
        date_columns=date_columns or [],
        datetime_columns=datetime_columns or [],
        int_columns=int_columns or [],
        json_columns=json_columns or [],
    )

    null_rate_by_column = {
        col: float(pd.isna(df[col]).mean()) for col in df.columns if pd.isna(df[col]).any()
    }

    orphaned_fk_rows_skipped: dict[str, int] = {}
    for check in fk_checks or []:
        if check.column not in df.columns:
            continue
        ref_table = cast(Table, check.referenced_model.__table__)
        valid_ids = {
            row[0]
            for row in conn.execute(ref_table.select().with_only_columns(
                ref_table.c[check.referenced_column]
            ))
        }
        is_null = pd.isna(df[check.column])
        allowed = is_null if check.nullable else pd.Series(False, index=df.index)
        allowed = allowed | df[check.column].isin(valid_ids)
        skipped = int((~allowed).sum())
        if skipped:
            orphaned_fk_rows_skipped[check.column] = skipped
            df = df[allowed]

    records: list[dict[str, Any]] = [
        {str(k): _none_if_na(v) for k, v in row.items()} for row in df.to_dict(orient="records")
    ]
    records, required_field_null_rows_dropped = _apply_not_null_defaults_or_drop(records, table)

    rows_inserted = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        if not batch:
            continue
        # No index_elements: the dataset's documented ~2% duplicate rate
        # (docs/data-lineage.md § 2) shows up on secondary unique columns too
        # (e.g. products.product_number), not just the primary key — an
        # unrestricted ON CONFLICT DO NOTHING treats any unique/exclusion
        # violation on the table as a skippable duplicate, not just a PK clash.
        #
        # psycopg's cursor.rowcount is -1 (unknown) for a multi-row VALUES
        # insert like this one — RETURNING + counting the returned rows is
        # the only reliable way to know how many actually inserted (rows
        # skipped by ON CONFLICT DO NOTHING produce no RETURNING row).
        stmt = (
            pg_insert(table)
            .values(batch)
            .on_conflict_do_nothing()
            .returning(*table.primary_key.columns)
        )
        result = conn.execute(stmt)
        rows_inserted += len(result.fetchall())

    return TableQualityReport(
        table_name=table_name,
        source_row_count=source_row_count,
        duplicates_removed=duplicates_removed,
        orphaned_fk_rows_skipped=orphaned_fk_rows_skipped,
        null_rate_by_column=null_rate_by_column,
        rows_loaded=rows_inserted,
        elapsed_seconds=time.monotonic() - start,
        required_field_null_rows_dropped=required_field_null_rows_dropped,
    )
