# Golden Cases

Machine-readable synthetic scenario fixtures backing `docs/demo-script.md` and the adversarial/
reliability requirements in `docs/guardrails.md` § 4 and `docs/evaluation-plan.md` § 11. These
are hand-authored, entirely synthetic (`docs/data-governance.md` § 6) — none reference real
customer data, and none of the expected outcomes are business-approved thresholds; they encode
the *structure* of a correct response, not an approved numeric policy.

**Status: fixtures only, `PLANNED` runner.** No test runner consumes these yet
(`docs/implementation-roadmap.md` Phase 6 onward wires the orchestrator against them; Phase 11
wires `python -m evaluation.run` to score against them). Until then, use them as the concrete
spec for `docs/demo-script.md` and as review material for the `investigate-fraud` and
`qa-engineer` workflows.

## Schema

Each case is a JSON file, `<case_id>.json`, with the following fields (all present in every
case; use `null` or an empty list/object rather than omitting a field):

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | Matches the filename stem |
| `purpose` | string | What this case is meant to prove |
| `demo_script_scenario` | string | Cross-reference to the `docs/demo-script.md` scenario letter |
| `language` | string | BCP-47-ish tag: `es-MX`, `es-CO`, or `es-AR` |
| `synthetic_input` | object | `{ "customer_message": string, "channel": string }` — the triggering input |
| `available_facts` | object | Facts the system should be able to retrieve (`docs/domain-model.md` § Fact) |
| `evidence` | array | Each item: `{ "type", "direction" ("supports_fraud"\|"supports_legitimate"\|"neutral"), "confidence" (0-1), "source" }` |
| `missing_information` | array of strings | Information the case deliberately withholds |
| `contradictory_evidence` | array of strings | Pairs/descriptions of evidence that conflict, if any (empty list if none) |
| `expected_ai_behavior` | string | What the LLM/orchestration layer should propose |
| `expected_policy_behavior` | string | What the deterministic policy engine should decide |
| `expected_human_involvement` | string | `none` \| `optional` \| `required` — and why |
| `prohibited_outcome` | string | An outcome that would represent a guardrail failure if it occurred |
| `expected_audit_events` | array of strings | Event types the audit log must contain after processing this case |

## Cases in this directory

| File | Scenario | Demo script ref |
|---|---|---|
| `legitimate_transaction.json` | Clean transaction, should auto-resolve without friction | Scenario A |
| `clear_fraud.json` | Strong fraud indicators, should protect + escalate the irreversible step | Scenario B |
| `ambiguous_transaction.json` | Mixed signals, should ask one targeted question or escalate | Scenario C |
| `high_value_transfer.json` | $100,000 transfer, human approval required regardless of confidence | Scenario D |
| `prompt_injection.json` | Adversarial instruction embedded in customer text | Scenario G |
| `missing_data.json` | Orphaned device reference / null fields | Scenario H |
| `conflicting_evidence.json` | Directly contradictory signals | Scenario I |
| `dependency_failure.json` | LLM and fraud-model unavailability | Scenarios E, F |
| `duplicate_action.json` | Same action submitted twice | Scenario J |
| `human_escalation.json` | Policy-ambiguous case requiring a full case packet | Scenario K |

`policy_rejection` (Scenario L in `docs/demo-script.md`) is intentionally not a separate fixture
here — it's better expressed as a follow-up action on `clear_fraud.json` (attempting a second
dispute on an already-resolved case) once the orchestrator exists to sequence it; add
`policy_rejection.json` at that point rather than fabricating a standalone case now.

## Adding a case

New cases must follow the schema above exactly, be clearly synthetic, and state a
`prohibited_outcome` that a test can actually assert against — a case with no falsifiable
prohibited outcome isn't pulling its weight as a regression fixture.
