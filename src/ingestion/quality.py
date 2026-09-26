"""Data-quality reporting (docs/data-lineage.md § 7).

Checks against the dataset's own documented baselines (docs/data-lineage.md
§ 2: ~2% duplicates, ~5% nulls in nullable fields) rather than inventing new
thresholds — a deviation from those documented baselines is what's worth
flagging, not the mere presence of duplicates/nulls the dataset creators
already told us to expect.
"""

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Any

EXPECTED_DUPLICATE_RATE = 0.02
EXPECTED_NULL_RATE = 0.05
# Deviation beyond this multiple of the expected rate is flagged, not just
# logged — e.g. actual duplicate rate > 2x the documented ~2% baseline.
FLAG_MULTIPLE = 2.0


@dataclasses.dataclass
class TableQualityReport:
    table_name: str
    source_row_count: int
    duplicates_removed: int
    orphaned_fk_rows_skipped: dict[str, int]
    null_rate_by_column: dict[str, float]
    rows_loaded: int
    elapsed_seconds: float
    required_field_null_rows_dropped: int = 0
    flags: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        if self.source_row_count:
            duplicate_rate = self.duplicates_removed / self.source_row_count
            if duplicate_rate > EXPECTED_DUPLICATE_RATE * FLAG_MULTIPLE:
                self.flags.append(
                    f"duplicate rate {duplicate_rate:.1%} exceeds "
                    f"{FLAG_MULTIPLE}x the documented ~{EXPECTED_DUPLICATE_RATE:.0%} baseline"
                )
        for column, rate in self.null_rate_by_column.items():
            if rate > EXPECTED_NULL_RATE * FLAG_MULTIPLE:
                self.flags.append(
                    f"column '{column}' null rate {rate:.1%} exceeds "
                    f"{FLAG_MULTIPLE}x the documented ~{EXPECTED_NULL_RATE:.0%} baseline"
                )
        if self.source_row_count and self.required_field_null_rows_dropped:
            rate = self.required_field_null_rows_dropped / self.source_row_count
            if rate > EXPECTED_NULL_RATE:
                self.flags.append(
                    f"{self.required_field_null_rows_dropped} rows "
                    f"({rate:.1%}) dropped for a NULL in a schema-required column - "
                    "exceeds the documented ~5% null baseline even for supposedly "
                    "mandatory fields"
                )


@dataclasses.dataclass
class IngestionReport:
    run_started_at: dt.datetime
    mode: str  # "sample" or "full"
    sample_days: int | None
    tables: list[TableQualityReport] = dataclasses.field(default_factory=list)
    skipped_tables: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_started_at": self.run_started_at.isoformat(),
            "mode": self.mode,
            "sample_days": self.sample_days,
            "tables": [dataclasses.asdict(t) for t in self.tables],
            "skipped_tables": self.skipped_tables,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")

    def print_summary(self) -> None:
        print(f"\nIngestion report ({self.mode}, sample_days={self.sample_days})")
        print(f"{'table':<28}{'source':>10}{'dupes':>8}{'loaded':>10}  flags")
        for t in self.tables:
            flag_str = "; ".join(t.flags) if t.flags else "-"
            print(
                f"{t.table_name:<28}{t.source_row_count:>10}{t.duplicates_removed:>8}"
                f"{t.rows_loaded:>10}  {flag_str}"
            )
        if self.skipped_tables:
            print(f"\nSkipped (out of workflow scope): {', '.join(self.skipped_tables)}")
