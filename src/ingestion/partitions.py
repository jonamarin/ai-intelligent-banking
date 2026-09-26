"""Discovers CSV files under the dataset's Hive-style year=/month=/day=
partitioning (docs/data-lineage.md § 1) and selects a bounded recent-date
sample for local development, or the full history for a batch/evaluation run.
"""

import datetime as dt
from pathlib import Path


def discover_partition_files(table_dir: Path) -> dict[dt.date, Path]:
    """Map each partition's date -> its single CSV file.

    Assumes the documented layout: <table_dir>/year=YYYY/month=MM/day=DD/*.csv
    """
    files: dict[dt.date, Path] = {}
    for csv_path in table_dir.glob("year=*/month=*/day=*/*.csv"):
        day_dir = csv_path.parent
        month_dir = day_dir.parent
        year_dir = month_dir.parent
        try:
            year = int(year_dir.name.split("=", 1)[1])
            month = int(month_dir.name.split("=", 1)[1])
            day = int(day_dir.name.split("=", 1)[1])
            files[dt.date(year, month, day)] = csv_path
        except (IndexError, ValueError):
            continue  # unexpected directory name — skip rather than crash
    return files


def select_recent_days(files_by_date: dict[dt.date, Path], sample_days: int) -> list[Path]:
    """Return the `sample_days` most recent partitions' file paths, sorted
    oldest-first (so a Phase 4 rolling-window feature could process them in
    order without re-sorting)."""
    ordered_dates = sorted(files_by_date.keys(), reverse=True)[:sample_days]
    return [files_by_date[d] for d in sorted(ordered_dates)]


def select_all(files_by_date: dict[dt.date, Path]) -> list[Path]:
    return [files_by_date[d] for d in sorted(files_by_date.keys())]
