"""Ingestion CLI entry point.

    uv run python -m src.ingestion.run                    # sample mode, 30 most recent days
    uv run python -m src.ingestion.run --sample-days 90
    uv run python -m src.ingestion.run --full              # entire dataset (slow — see README)

Loads, in FK-dependency order: customers, products, daily_exchange_rates
(independent) -> transactions, call_center_interactions -> call_transcripts,
complaints -> digital_events. `branches`, `service_agents`,
`marketing_campaigns`, `campaign_sends`, `satisfaction_surveys` are
deliberately skipped — out of this workflow's scope
(docs/data-dictionary.md § Tables not used).
"""

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from src.ingestion.loader import ForeignKeyCheck, load_table
from src.ingestion.partitions import discover_partition_files, select_all, select_recent_days
from src.ingestion.quality import IngestionReport
from src.models import (
    CallCenterInteraction,
    CallTranscript,
    Complaint,
    Customer,
    DigitalEvent,
    ExchangeRate,
    Product,
    Transaction,
)
from src.models.base import get_engine

DEFAULT_SAMPLE_DAYS = 30
RAW_DATA_DIR = Path("data/raw/data")
SKIPPED_TABLES = [
    "branches",
    "service_agents",
    "marketing_campaigns",
    "campaign_sends",
    "satisfaction_surveys",
]


def _partition_paths(table: str, *, full: bool, sample_days: int) -> list[Path]:
    files_by_date = discover_partition_files(RAW_DATA_DIR / table)
    return select_all(files_by_date) if full else select_recent_days(files_by_date, sample_days)


def run(
    *,
    full: bool,
    sample_days: int,
    report_path: Path,
    skip_tables: set[str] | None = None,
) -> IngestionReport:
    """`skip_tables` selectively skips loadable tables beyond the permanently
    out-of-scope SKIPPED_TABLES — e.g. Phase 4 doesn't need digital_events or
    call_transcripts, and skipping them keeps a longer transactions/complaints
    history load within this environment's tight memory budget
    (src/ingestion/README.md § Sample vs. full mode)."""
    skip_tables = skip_tables or set()
    report = IngestionReport(
        run_started_at=dt.datetime.now(dt.UTC),
        mode="full" if full else "sample",
        sample_days=None if full else sample_days,
        skipped_tables=SKIPPED_TABLES + sorted(skip_tables),
    )

    engine = get_engine()
    with engine.begin() as conn:

        def load(name: str, **kwargs: Any) -> None:
            if name in skip_tables:
                return
            report.tables.append(load_table(conn, **kwargs))

        load(
            "customers",
            model=Customer,
            csv_paths=[RAW_DATA_DIR / "customers.csv"],
            pk_columns=["customer_id"],
            bool_columns=["accepts_marketing"],
            date_columns=["date_of_birth"],
            datetime_columns=["registration_date", "last_updated"],
            int_columns=["credit_score"],
        )
        load(
            "products",
            model=Product,
            csv_paths=[RAW_DATA_DIR / "products.csv"],
            pk_columns=["product_id"],
            bool_columns=["has_linked_app"],
            date_columns=["opening_date", "expiration_date"],
            datetime_columns=["last_transaction_date", "last_updated"],
            int_columns=["days_past_due"],
            fk_checks=[ForeignKeyCheck("customer_id", Customer, "customer_id", nullable=False)],
        )
        load(
            "daily_exchange_rates",
            model=ExchangeRate,
            csv_paths=[RAW_DATA_DIR / "daily_exchange_rates.csv"],
            pk_columns=["date", "source_currency", "target_currency"],
            date_columns=["date"],
        )
        load(
            "transactions",
            model=Transaction,
            csv_paths=_partition_paths("transactions", full=full, sample_days=sample_days),
            pk_columns=["transaction_id"],
            bool_columns=["is_fraud"],
            datetime_columns=["transaction_date"],
            date_columns=["process_date"],
            fk_checks=[
                ForeignKeyCheck("customer_id", Customer, "customer_id", nullable=False),
                ForeignKeyCheck("product_id", Product, "product_id", nullable=False),
            ],
        )
        load(
            "call_center_interactions",
            model=CallCenterInteraction,
            csv_paths=_partition_paths(
                "call_center_interactions", full=full, sample_days=sample_days
            ),
            pk_columns=["interaction_id"],
            bool_columns=[
                "was_resolved",
                "requires_followup",
                "was_escalated",
                "has_transcript",
                "has_recording",
            ],
            datetime_columns=["interaction_date"],
            date_columns=["process_date"],
            int_columns=["duration_seconds", "wait_time_seconds"],
            fk_checks=[ForeignKeyCheck("customer_id", Customer, "customer_id", nullable=False)],
        )
        load(
            "call_transcripts",
            model=CallTranscript,
            csv_paths=_partition_paths("call_transcripts", full=full, sample_days=sample_days),
            pk_columns=["transcript_id"],
            date_columns=["process_date"],
            int_columns=["duration_seconds"],
            json_columns=["mentioned_entities"],
            fk_checks=[
                ForeignKeyCheck(
                    "interaction_id", CallCenterInteraction, "interaction_id", nullable=False
                ),
                ForeignKeyCheck("customer_id", Customer, "customer_id", nullable=False),
            ],
        )
        load(
            "complaints",
            model=Complaint,
            csv_paths=_partition_paths("complaints", full=full, sample_days=sample_days),
            pk_columns=["complaint_id"],
            bool_columns=["sla_breached", "is_repeat_complainer"],
            datetime_columns=[
                "creation_date",
                "assignment_date",
                "first_response_date",
                "resolution_date",
                "closing_date",
            ],
            date_columns=["process_date"],
            int_columns=["resolution_days", "resolution_satisfaction"],
            fk_checks=[
                ForeignKeyCheck("customer_id", Customer, "customer_id", nullable=False),
                ForeignKeyCheck("affected_product_id", Product, "product_id", nullable=True),
                ForeignKeyCheck(
                    "origin_interaction_id",
                    CallCenterInteraction,
                    "interaction_id",
                    nullable=True,
                ),
            ],
        )
        load(
            "digital_events",
            model=DigitalEvent,
            csv_paths=_partition_paths("digital_events", full=full, sample_days=sample_days),
            pk_columns=["event_id"],
            bool_columns=["is_mobile"],
            datetime_columns=["event_date"],
            date_columns=["process_date"],
            int_columns=["duration_seconds"],
            fk_checks=[
                ForeignKeyCheck("customer_id", Customer, "customer_id", nullable=True),
                ForeignKeyCheck("product_id", Product, "product_id", nullable=True),
            ],
        )

    report.print_summary()
    report.save(report_path)
    print(f"\nFull report written to {report_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="Load the entire dataset instead of a recent sample."
    )
    parser.add_argument(
        "--sample-days",
        type=int,
        default=DEFAULT_SAMPLE_DAYS,
        help=f"Days of partitioned fact tables to load (default {DEFAULT_SAMPLE_DAYS}). "
        "Ignored with --full.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("data/reports/ingestion_report.json"),
    )
    parser.add_argument(
        "--skip-tables",
        type=str,
        default="",
        help="Comma-separated loadable table names to skip this run (e.g. "
        "'digital_events,call_transcripts' to save memory/time when a phase doesn't need them).",
    )
    args = parser.parse_args()
    skip_tables = {t.strip() for t in args.skip_tables.split(",") if t.strip()}
    run(
        full=args.full,
        sample_days=args.sample_days,
        report_path=args.report_path,
        skip_tables=skip_tables,
    )


if __name__ == "__main__":
    main()
