# Ingestion

Loads the LATAM Bank dataset from `data/raw/` (`docs/data-lineage.md` § 1) into the schema
created in Phase 2. Entry point:

```
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m src.ingestion.run [--full] [--sample-days N] [--report-path PATH]
```

(Override `DATABASE_URL` as shown when running from the host against the `docker compose`
`db` service — see `CLAUDE.md` § 9 for why.)

## Sample vs. full mode

Default: **sample mode**, the most recent 30 days of each date-partitioned fact table
(`--sample-days` to change it). Dimension tables (`customers`, `products`,
`daily_exchange_rates`) always load in full regardless — they're small (150k/400k/3k rows).

`--full` loads the entire ~3-year history of every fact table instead. **This has not been run
in this environment** — the machine this pipeline was built and verified on has very little
free RAM (observed as low as ~1.5 GB free of 16 GB total, likely from other running
applications), and a `--sample-days 3` run alone was killed twice by out-of-memory conditions
before a fix (see below) and a smaller sample got it through. A `--full` run of `digital_events`
alone (10M rows) is very likely to need considerably more free memory and time than was
available here. Before running `--full` anywhere:
- Confirm the target machine has several GB of free RAM headroom beyond what's already in use.
- Consider running table-by-table rather than all at once if memory is tight (the tables are
  independent enough in `run.py` that this is a straightforward split).
- Expect it to take considerably longer than the sample run — budget accordingly rather than
  assuming linear scaling from the sample timings below is exact.

Verified sample run (`--sample-days 3`, this environment, 2026-09-25): all 8 loaded tables'
row counts matched the live database exactly (`docs/project-status.md` § Phase 3 detail) in a
few minutes.

## What gets loaded, and what doesn't

Loaded: `customers`, `products`, `daily_exchange_rates`, `transactions`,
`call_center_interactions`, `call_transcripts`, `complaints`, `digital_events` — the tables this
workflow actually uses (`docs/data-dictionary.md`). Skipped, deliberately: `branches`,
`service_agents`, `marketing_campaigns`, `campaign_sends`, `satisfaction_surveys` (out of
workflow scope, same reference).

## Data-quality handling (docs/data-lineage.md § 2, § 7)

- **Duplicates:** rows are deduplicated on the primary key within each load; at the database
  level, `INSERT ... ON CONFLICT DO NOTHING` is unrestricted (not scoped to the PK index),
  because the dataset's documented ~2% duplicate rate shows up on secondary unique columns too
  (e.g. `products.product_number` collided across different `product_id`s in real data observed
  here) — an unrestricted `ON CONFLICT DO NOTHING` treats any unique-constraint violation as a
  skippable duplicate rather than a fatal error.
- **Orphaned foreign keys:** a row whose FK doesn't match anything already loaded is dropped and
  counted (`orphaned_fk_rows_skipped` in the report), not left to crash the insert or produce a
  broken reference — matching the dataset's documented small orphan rate.
- **NULLs in "required" fields:** the data violates its own documented NOT NULL constraints
  sometimes (observed here: `call_transcripts.duration_seconds`, documented NOT NULL, was NULL
  in 12.2% of a real 3-day sample). For each schema NOT NULL column: if it has a declared
  Python-side default, a NULL value is dropped from the row (letting the default apply);
  otherwise the whole row is dropped and counted
  (`required_field_null_rows_dropped`) rather than crashing or silently inserting a wrong value.
- **Null-rate / duplicate-rate flags:** the report flags any column/table whose actual rate
  exceeds 2x the dataset's own documented baseline (~5% nulls, ~2% duplicates) — informational,
  not a hard failure; real null rates on genuinely optional columns in this dataset are often
  well above the documented aggregate baseline, and that's expected, not a bug.

## A real pandas-version bug found here (worth knowing if you touch this code)

`loader.py`'s null/NA handling exists in its current form (`pd.isna(...)` everywhere, a single
`_none_if_na` normalization at record-build time) because of a real bug caught during
verification: pandas >= 3.0 gives plain string columns a dedicated `str` dtype whose missing
marker is `float('nan')`, not `None`, and unlike pandas < 3.0, `.where(df.notnull(), None)` does
**not** reliably convert it. A `value is None` check silently saw zero matches on a column that
was actually 86/217 null, which meant every row with a null-but-*allowed* nullable foreign key
got treated as an *orphan* and dropped instead. Caught by comparing the ingestion report's
counts against the live database's actual row counts (`docs/project-status.md` § Phase 3
detail) — they didn't match, which is what should always be checked, not just "the script
exited 0". Regression tests: `tests/unit/test_ingestion_loader.py`.

## Report

Every run writes a JSON report (default `data/reports/ingestion_report.json`, committed to git
as evidence — it's small aggregate stats, no raw data) and prints a summary table. See
`src/ingestion/quality.py` for the exact schema.
