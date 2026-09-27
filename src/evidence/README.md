# Evidence Engine (Phase 5)

```
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m src.evidence.build_case --refresh-devices --pick-fraud
# or a specific transaction:
DATABASE_URL="..." uv run python -m src.evidence.build_case --transaction-id <ID>
```

Builds a structured evidence graph for one transaction — what supports fraud, what supports
legitimacy, what's unknown, and what contradicts what (`docs/domain-model.md` § Evidence Graph,
`prompt.md` § 10) — and persists it as real rows (`fraud_cases`, `evidence`, `audit_events`).
**Never collapses to a single score**, and **never authorizes anything** — this module answers
"what does the evidence suggest," not "what action is allowed." That's the Policy Engine's job
(Phase 7, doesn't exist yet); this module must never be wired to a tool that executes an action.

## Modules

- `device.py` — derives the `Device` entity from `digital_events`. **Read the module
  docstring first**: the dataset has no persistent device-fingerprint column, so `device_id`
  is a documented heuristic proxy (`sha256(ip_address, platform, browser)`), with known,
  stated limitations (NAT/shared-network collisions, IP changes registering as "new device").
  Missing `ip_address` → `Unknown`, never a fabricated stable ID.
- `graph.py` — the six evidence-extraction rules (device history, country deviation, amount
  deviation, auth result, historical dispute rate, velocity), each producing an `EvidenceItem`
  with `direction`/`confidence`/`provenance`; contradiction detection (any two non-neutral
  items whose directions disagree, both above a confidence threshold).
- `persist.py` — writes the graph as a `FraudCase` + `Evidence` rows (append-only) + one
  `AuditEvent`. Deliberately does **not** set `risk_score` or create a `Decision` — that needs
  the Phase 4 model and Phase 7 policy engine wired together (Phase 6's orchestration job).
- `build_case.py` — the CLI tying it together.

## Verified result (2026-09-26)

Ran against the real loaded sample (`docs/project-status.md` § Phase 3/4 detail: 90-day
transactions, 7-day `digital_events`). `--refresh-devices` derived **19,065 distinct device
fingerprints from 112,692 digital_events**. Two real seeded cases committed as evidence
(`data/reports/example_evidence_graph*.json`):

1. **A real `is_fraud=true` transaction** (`TRX-MXCWNPT6UVBUMBBVOPWM`) — evidence came back
   almost entirely `supports_legitimate`/`neutral` (matching country, unremarkable amount,
   successful auth, no complaints, no velocity spike, no nearby digital session to assess
   device on). **Consistent with the Phase 4 finding**, not contradicting it: the behavioral
   signals available don't flag this case, reinforcing that whatever signal produces
   `is_fraud`/`fraud_score` in this dataset isn't fully captured by these features.
2. **A real `is_fraud=false` (legitimate) transaction** (`TRX-SMPYV51IQT9JPNQ56BMR`) —
   known device (seen before for this customer), matching country, successful auth, but an
   amount 4.3 standard deviations above this customer's prior mean. **The engine correctly
   flagged 2 contradictions** (the anomalous-amount evidence vs. the known-device and
   matching-country evidence) rather than picking a side — exactly the "ambiguous, mixed
   evidence" case `docs/demo-script.md` Scenario C describes, found in real data, not
   hand-constructed for the demo.

## Two real bugs found and fixed during verification

1. **Parameter-limit bug, again:** `load_devices` inserted all derived devices in one
   unbatched `INSERT`, hitting Postgres's 65,535-parameter cap for ~19k device rows — the same
   bug class already fixed once in `src/ingestion/loader.py`, reintroduced here because this
   module didn't reuse that helper. Fixed with the same batching + `RETURNING`-based row count.
2. **ID length mismatch:** `fraud_cases.case_id` is `VARCHAR(30)` but the code generated full
   36-character UUIDs for it (correct for `evidence.evidence_id`, which is `VARCHAR(36)`, but
   not for `case_id`) — caught as a `StringDataRightTruncation` error on the first real
   persist attempt, not by code review. Fixed with a dedicated, shorter ID scheme for cases.
3. **Enum storage inconsistency** (not a crash, but a real correctness bug): SQLAlchemy's
   `Enum(native_enum=False)` stores the Python member *name* (`SUPPORTS_FRAUD`) by default, not
   `.value` (`supports_fraud`) — inconsistent with `docs/domain-model.md`'s documented direction
   strings and this module's own `to_dict()` output. Caught by inspecting the first real rows
   written to the `evidence` table. Fixed with `values_callable` on the column definition; no
   migration was needed once traced down — `validate_strings=True` turned out to be
   Python-side-only, with no corresponding database CHECK constraint to alter.

## What this phase does not do

Compute or store a risk score, make a policy decision, or execute any action. Those remain
Phases 4 (model, already done, not yet wired here), 6 (orchestration), and 7 (policy engine).
`digital_events` is loaded for only a 7-day window (not the full 90 days transactions cover) —
device evidence for transactions outside that window is honestly `Unknown`, not guessed.
