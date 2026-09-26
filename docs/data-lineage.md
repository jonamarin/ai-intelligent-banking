# Data Lineage

Owns: movement and transformation of data. See `docs/data-governance.md` for the rules
governing that movement, and `docs/data-dictionary.md` for the schema of each table named
here.

## 1. Source

**LATAM Bank Dataset**, Factored Datathon 2026, version 1.0.0, generated July 2026: ~19M rows
across 13 tables, covering Mexico, Colombia, and Argentina, June 2023 – June 2026, entirely
**synthetic**. Full schema documentation: `LATAM_Bank_Complete_Data_Dictionary.pdf` and
`LATAM_Bank_Dataset_Summary.pdf` at the repository root (source of truth for exact
column-level detail — `docs/data-dictionary.md` is a derived, greppable translation, not a
replacement).

**Raw files status (updated 2026-09-25): downloaded locally.** The organizer-provided,
read-only S3 bucket (`factored-datathon-2026-s3-157725502942-us-east-2-an`, region
`us-east-2` — organizer-approved per `project_presentation.txt` § Data and execution
boundaries) was synced to `data/raw/` (~5.0 GB, 7,672 files). `data/raw/` is excluded from git
(`.gitignore`) and must stay that way — the dataset is large, and access is credentialed even
though it's read-only; it does not belong in version control. **Access credentials are never
stored in this repository** — they live only in the local machine's `~/.aws/credentials`
(outside the repo), configured via `aws configure`. If the credentials need rotating or
sharing with a teammate, do that out-of-band, never by adding them to a file here.

Format and layout as downloaded:
- Dimension/reference tables are flat CSVs at `data/raw/data/<table>.csv` (`customers.csv`,
  `products.csv`, `branches.csv`, `service_agents.csv`, `marketing_campaigns.csv`,
  `daily_exchange_rates.csv`).
- Fact tables are Hive-style date-partitioned CSVs:
  `data/raw/data/<table>/year=YYYY/month=MM/day=DD/<table>_YYYYMMDD.csv`
  (`transactions/`, `call_center_interactions/`, `call_transcripts/`, `satisfaction_surveys/`,
  `digital_events/`, `complaints/`, `campaign_sends/`), matching the "daily" partition noted
  in `docs/data-dictionary.md`.
- A duplicate top-level `marketing_campaigns.csv` also exists outside `data/`; the one under
  `data/raw/data/` is the one described in the data dictionary and is what ingestion should
  use. A separate `data_backup_20260831/` prefix exists in the bucket and was intentionally
  **not** synced (appears to be a redundant snapshot; re-evaluate only if the primary `data/`
  prefix is found to be incomplete or stale).

Ingestion into PostgreSQL (Phase 3, `docs/implementation-roadmap.md`) is **implemented and
verified** for a bounded recent-date sample (`src/ingestion/`, `docs/project-status.md` § Phase
3 detail) — a `--full` run of the entire dataset has not yet been done in this environment
(`src/ingestion/README.md` § Sample vs. full mode).

## 2. Documented data-quality characteristics (from the source docs — not this project's
   finding)

- Duplicate records: ~2% across tables.
- Null values: ~5% in nullable fields.
- Late arrivals: partitioned data may arrive late.
- Schema evolution: table schemas may change over time.
- Referential integrity mostly maintained, with a small percentage of intentionally orphaned
  records for testing.

Any ingestion pipeline must validate for and handle these explicitly (dedup logic, null
handling per field, late-arrival tolerance in partition processing, schema-version checks) —
they are not edge cases, they are documented properties of the dataset.

## 3. Lineage by consumer

| Data | Source table(s) | Transformation | Destination | Consumers |
|---|---|---|---|---|
| Transaction facts | `transactions` | Currency conversion via `daily_exchange_rates` where `amount_usd` is missing/stale; masking of any raw identifiers before LLM context | Case/Evidence records | Evidence Engine, Fraud/Risk Model, Decision Engine |
| Customer context | `customers` | Field-level minimization (`docs/data-governance.md` § 2) | Evidence records | Evidence Engine, Conversation Intelligence |
| Device/session signal | `digital_events` | Derivation of a `Device` entity (`docs/domain-model.md` § Device) — not a 1:1 table mapping | Evidence records | Evidence Engine, Fraud/Risk Model |
| Merchant signal | `transactions.merchant_name` / `merchant_category` | Derivation of a `Merchant` entity and aggregated risk/chargeback-rate features | Evidence records, model features | Fraud/Risk Model |
| Prior disputes | `complaints` | Filtered to the customer/product, used as a historical-dispute-rate feature and for `is_repeat_complainer` signal | Model features, Evidence records | Fraud/Risk Model, Evidence Engine |
| Customer statement | `call_center_interactions`, `call_transcripts`, or a live chat message | None (kept verbatim, treated as untrusted) | Case record | Conversation Intelligence, Case Packet (`docs/human-oversight.md` § 3) |
| Model output | (generated at runtime) | None | Decision record | Decision Engine, Audit Log |
| Policy decision | (generated at runtime) | None | Decision record | Decision Engine, Action Gateway, Audit Log |
| Audit events | (generated at runtime) | Redaction (`docs/observability.md` § 2) applied before write | Audit Log | Observability, Human Review |

## 4. Feature derivation (fraud model)

Features listed in `docs/model-evaluation.md` § 4 are derived from the tables above at
scoring time, using only data available *before* the transaction being scored completed
(temporal integrity — see § 5 below). Exact derivation logic is `PLANNED`, to be implemented
and documented feature-by-feature in Phase 4 (`docs/implementation-roadmap.md`); this document
records where each feature's raw inputs come from so that implementation isn't guessing at
schema.

## 5. Leakage

**`transactions.fraud_score` and `transactions.is_fraud` are excluded from model features.**
`fraud_score` in particular is very likely a synthetic label-generation artifact (possibly
itself the output of the process that generated `is_fraud`), not a signal a production system
would have had access to at transaction time. Using either as a feature would leak the
evaluation target into the model. They may be referenced only as a `SYNTHETIC` comparison
point in evaluation write-ups, explicitly labeled as such, never as a model input or as this
project's own fraud determination.

## 6. Sensitivity and retention per flow

See `docs/data-governance.md` § 1 (classification) and § 4 (retention — `TBD`). This document
does not restate those rules; it maps which flows carry which classes of data so the rules are
easy to apply during implementation.

## 7. Quality checks

**Implemented** (`src/ingestion/`, Phase 3 — see `docs/project-status.md` § Phase 3 detail and
`src/ingestion/README.md`): duplicate detection (deduplicated on primary key per load, plus an
unrestricted `ON CONFLICT DO NOTHING` at the database level since the documented ~2% duplicate
rate also shows up on secondary unique columns, not just primary keys — observed directly on
`products.product_number`), referential-integrity checks with orphaned rows dropped and
counted rather than crashing the load, and null-rate checks flagged when a column's actual
rate exceeds 2x the documented ~5% baseline. Schema-required (NOT NULL) columns that the real
data violates anyway are handled explicitly: fall back to a declared default, or drop and count
the row — discovered to be a real, not hypothetical, issue
(`call_transcripts.duration_seconds`, documented NOT NULL, was null in 12.2% of one sample).
Timestamp/currency plausibility checks beyond type coercion are not implemented — `PLANNED`,
revisit if Phase 4 feature engineering needs them. The data-quality report format is a JSON
file per run (`src/ingestion/quality.py`), example committed at
`data/reports/ingestion_report.json`.
