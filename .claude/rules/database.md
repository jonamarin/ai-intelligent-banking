# Database Rules

Applies to schema, migrations, and query code once Phase 2 (`docs/implementation-roadmap.md`)
starts. See `docs/domain-model.md` for the entities being modeled and `docs/data-lineage.md`
for the source dataset's documented quality characteristics migrations must tolerate.

- Every schema change is a migration, generated and reviewed — never a manual `ALTER` against
  a running database, never a destructive migration without an explicit rollback path.
- Index `customer_id`, `transaction_id`, `case_id`, `timestamp`, `device_id`, and `merchant_id`
  wherever they appear as foreign keys or common filter columns (`prompt.md` § 45).
- Use database transactions for any multi-statement financial state change; a partial write on
  a financial record is not an acceptable failure mode.
- Every state-changing operation is idempotent — design the schema (unique idempotency-key
  constraints where relevant) to make double-execution structurally hard, not just
  policy-forbidden (`docs/architecture.md` § 11).
- Handle the dataset's documented data-quality characteristics explicitly in ingestion/query
  code: ~2% duplicates, ~5% nulls in nullable fields, late-arriving partitions, occasional
  orphaned foreign keys (`docs/data-lineage.md` § 2) — do not assume clean joins.
- Evidence and audit records are append-only — no `UPDATE`/`DELETE` path exists for them at
  the schema or application level (`docs/guardrails.md` § 4).
- Sensitive fields (documented in `docs/data-governance.md` § 1) are flagged in the model/
  migration itself (docstring or column comment), so their classification is visible at the
  schema level, not only in a separate doc.
- Concurrency: financial balance/state updates use appropriate locking or optimistic
  concurrency control — never a read-then-write race on a monetary field.
- Retention: do not implement a "keep forever" default for any table without checking
  `docs/data-governance.md` § 4 (currently `TBD`) — leave retention configurable rather than
  hardcoding an assumption either way.
- Never run a destructive operation (`DROP`, `TRUNCATE`, a migration that deletes data) against
  anything but a local/throwaway development database without explicit user authorization for
  that specific action.
