---
description: Workflow for creating a database migration in this repository. Use whenever a schema change is needed (new table, column, index, constraint) once the database layer exists (Phase 2 onward).
---

# Create Migration

Follow `.claude/rules/database.md` throughout. Before writing a migration:

1. **Confirm the entity/field maps to `docs/domain-model.md`.** If it doesn't, check whether
   the domain model needs updating first (and whether that's a design decision worth an ADR —
   `docs/decisions/README.md`) rather than quietly adding a field the domain model doesn't
   describe.
2. **Check backward compatibility.** Does this migration break an existing consumer (API
   response shape, another table's foreign key, an existing query)? If so, plan an expand-then-
   contract sequence rather than a breaking single-step change.
3. **Review schema design:**
   - Index `customer_id`, `transaction_id`, `case_id`, `timestamp`, `device_id`,
     `merchant_id` wherever present.
   - Sensitive fields carry a classification note per `docs/data-governance.md` § 1.
   - Evidence/audit tables are append-only — no update/delete migration path for them.
   - Idempotency-key columns/constraints for any new state-changing action table.
4. **Plan migration safety:**
   - Is this migration reversible? Write the down-migration, or explicitly document why one
     isn't possible and what that means for rollback.
   - Does it lock a large table in a way that would be a problem at the dataset's actual scale
     (transactions: 5M rows, digital_events: 10M rows)? Prefer additive, non-locking changes
     where the migration tool supports it.
5. **Plan data migration strategy** separately from schema migration if existing data needs to
   be backfilled or transformed — don't conflate "change the schema" with "migrate the data"
   in a way that makes either one hard to reason about or roll back independently.
6. **Use transactions** for any migration step that must be atomic.
7. **Write tests** — at minimum, that the migration applies cleanly to a fresh database and
   that any new constraint actually rejects invalid data.

Never perform a destructive migration (dropping a column/table with data, an irreversible
transform) against anything but a local/throwaway development database without explicit user
authorization for that specific action (`.claude/rules/infrastructure.md`).
