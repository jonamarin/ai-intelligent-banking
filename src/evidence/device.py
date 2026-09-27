"""Device derivation from digital_events (docs/domain-model.md § Device).

**Important limitation, stated up front:** the LATAM Bank dataset has no
persistent device-fingerprint column — `digital_events` gives only
`ip_address`, `platform`, `browser`, `app_version`, `session_id`. This
module's `device_id` is therefore a **heuristic proxy**
(`sha256(ip_address, platform, browser)`), not a true device fingerprint:
- Multiple customers behind the same NAT/corporate network/shared Wi-Fi will
  collide onto one "device" — a known, real limitation of IP-based
  fingerprinting, not hidden here.
- A customer's own IP changing (mobile network, new Wi-Fi) will register as
  a "new device" even on the same physical phone.
- `app_version` is deliberately excluded from the fingerprint — it changes
  on every app update and would create false "new device" positives on an
  otherwise-unchanged phone.
When `ip_address` is missing (~5% of events in the loaded sample) no
fingerprint is computed — represented as `Unknown` (docs/domain-model.md §
4), never fabricated as a fake stable ID.
"""

import dataclasses
import datetime as dt
import hashlib
from typing import cast

import pandas as pd
from sqlalchemy import Table, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from src.models import Device


def compute_device_fingerprint(
    ip_address: str | None, platform: str | None, browser: str | None
) -> str | None:
    if not ip_address:
        return None  # no signal to fingerprint on — Unknown, not fabricated
    key = f"{ip_address}|{platform or ''}|{browser or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def derive_devices(digital_events: pd.DataFrame) -> pd.DataFrame:
    """One row per distinct device fingerprint seen in `digital_events`,
    aggregated exactly like the Device model's fields (src/models/device.py):
    first_seen, last_seen, customer_count (distinct customers who have used
    this fingerprint — a device used by many different customers is itself
    a fraud signal, e.g. a shared/compromised device or a fraud ring),
    operating_system/browser_family (most common values observed).
    """
    df = digital_events.copy()
    df["device_id"] = [
        compute_device_fingerprint(ip, plat, br)
        for ip, plat, br in zip(df["ip_address"], df["platform"], df["browser"], strict=True)
    ]
    df = df[df["device_id"].notna()]
    if df.empty:
        return pd.DataFrame(
            columns=[
                "device_id",
                "first_seen",
                "last_seen",
                "customer_count",
                "operating_system",
                "browser_family",
            ]
        )

    grouped = df.groupby("device_id").agg(
        first_seen=("event_date", "min"),
        last_seen=("event_date", "max"),
        customer_count=("customer_id", pd.Series.nunique),
        operating_system=("platform", lambda s: s.mode().iat[0] if not s.mode().empty else None),
        browser_family=("browser", lambda s: s.mode().iat[0] if not s.mode().empty else None),
    )
    return grouped.reset_index()


#  Postgres caps a single query at 65535 bound parameters — same limit hit
#  (and fixed the same way) in src/ingestion/loader.py. Device has 8 columns,
#  so 2000 rows/batch (~16,000 params) stays safely under it.
_BATCH_SIZE = 2_000


def load_devices(conn: Connection, devices: pd.DataFrame) -> int:
    """Upsert derived devices (device stats can legitimately be recomputed
    and updated as more events arrive — unlike Evidence, Device is not
    append-only, it's a rolling aggregate)."""
    if devices.empty:
        return 0
    table = cast(Table, Device.__table__)
    records = [{str(k): v for k, v in row.items()} for row in devices.to_dict(orient="records")]

    rows_affected = 0
    for i in range(0, len(records), _BATCH_SIZE):
        batch = records[i : i + _BATCH_SIZE]
        insert_stmt = pg_insert(table).values(batch)
        # cursor.rowcount is -1 (unknown) for a multi-row VALUES upsert under
        # psycopg (same issue fixed in src/ingestion/loader.py) — RETURNING +
        # counting the returned rows is exact regardless of driver support.
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["device_id"],
            set_={
                "last_seen": insert_stmt.excluded.last_seen,
                "customer_count": insert_stmt.excluded.customer_count,
                "operating_system": insert_stmt.excluded.operating_system,
                "browser_family": insert_stmt.excluded.browser_family,
            },
        ).returning(table.c.device_id)
        result = conn.execute(stmt)
        rows_affected += len(result.fetchall())
    return rows_affected


@dataclasses.dataclass
class DeviceHistory:
    device_id: str | None
    known_for_this_customer: bool | None  # None = Unknown (no fingerprint available)
    customer_count: int | None  # how many distinct customers have used this device, ever
    first_seen_for_customer: dt.datetime | None


def get_device_history(
    conn: Connection,
    *,
    customer_id: str,
    device_id: str | None,
    before: dt.datetime,
) -> DeviceHistory:
    """Strictly-prior device history for one customer/device pair — used by
    the Evidence Engine (graph.py), never by src/ml (bulk feature engineering
    has its own leakage-safe path; this is the single-case equivalent).

    Fingerprints are computed in Python via `compute_device_fingerprint` —
    the single source of truth for the hash — rather than reimplemented in
    SQL (which would need a cryptographic hash function that may not exist
    without an extension, and would risk silently drifting out of sync with
    the Python implementation). This customer's own event volume is small
    enough that pulling their rows and hashing in Python is cheap.
    """
    if device_id is None:
        return DeviceHistory(None, None, None, None)

    rows = conn.execute(
        text(
            """
            SELECT event_date, ip_address, platform, browser
            FROM digital_events
            WHERE customer_id = :customer_id AND event_date < :before
            """
        ),
        {"customer_id": customer_id, "before": before},
    ).fetchall()

    matching_dates = [
        row.event_date
        for row in rows
        if compute_device_fingerprint(row.ip_address, row.platform, row.browser) == device_id
    ]

    device_row = conn.execute(
        text("SELECT customer_count FROM devices WHERE device_id = :device_id"),
        {"device_id": device_id},
    ).fetchone()
    customer_count = device_row[0] if device_row else None

    return DeviceHistory(
        device_id=device_id,
        known_for_this_customer=bool(matching_dates),
        customer_count=customer_count,
        first_seen_for_customer=min(matching_dates) if matching_dates else None,
    )


def refresh_devices(engine: Engine, digital_events: pd.DataFrame) -> int:
    devices = derive_devices(digital_events)
    with engine.begin() as conn:
        return load_devices(conn, devices)
