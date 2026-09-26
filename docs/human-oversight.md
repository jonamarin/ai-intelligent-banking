# Human Oversight

Owns: review, approval, escalation, and override. See `docs/decision-policy.md` for how risk
and action-risk are computed, and `docs/guardrails.md` for how approval requirements are
enforced in code rather than only described here.

## 1. Decision categories

- **Automated decision:** the policy engine authorizes and the Action Gateway executes without
  a human in the loop (only for Low action-risk, low-risk-band cases where policy explicitly
  allows automation — `docs/decision-policy.md` § 5–6).
- **Assisted decision:** the AI proposes; a human must actively approve before execution.
- **Escalation:** the case is handed to a human for investigation and decision, with a
  structured packet (§ 3) — the AI does not propose a specific action, or its proposal is
  advisory only.

## 2. Approval matrix (conceptual — not approved policy)

| Action | AI | Deterministic Policy | Human |
|---|---|---|---|
| Explain transaction | Allowed | Where applicable | Not necessarily |
| Retrieve information | Allowed | Required | Not necessarily |
| Create low-risk case | Recommend | Required | Depending on policy |
| Ask verification question | Recommend | Required | Depending on policy |
| Create dispute | Recommend | Required | Depending on risk |
| Freeze card | Recommend | Required | Depending on policy |
| Large refund | Recommend | Required | Required where policy says |
| Account closure | Cannot independently authorize | Required | Required |
| Large transfer | Cannot independently authorize | Required | Required |

(`prompt.md` § 16.) This table is conceptual, mirrors `prompt.md` directly, and is not an
approved business policy — the "Depending on risk/policy" cells are `OPEN QUESTION` until a
policy owner sets concrete rules. Never hardcode numeric thresholds into this table without
that approval; encode them as configuration once approved.

## 3. Case packet (escalation contract)

When a case escalates, the human agent must receive a self-contained packet — they must never
need to reconstruct the case manually (`prompt.md` § 21):

- Case ID
- Customer statement (verbatim, in its original language)
- Transaction (facts, from `docs/domain-model.md` § Transaction)
- Risk score (labeled as a model prediction, with model version)
- Evidence supporting fraud
- Evidence supporting legitimacy
- Contradictions
- Model version, policy version
- Actions already performed (if any, with idempotency keys)
- Recommended next action (labeled as an AI recommendation, not a decision)
- Reason for escalation
- Confidence (and what it does and doesn't mean)
- Missing information

## 4. Reviewer context and override

The analyst view must present the evidence graph and both explanations (customer-facing and
analyst-facing, `prompt.md` § 22) without implying certainty the evidence doesn't support
(`docs/domain-model.md` § 4). A reviewer's override of the AI recommendation is recorded as a
distinct `Human Review` record (never merged into the `Decision` record), with the reviewer's
identity and rationale (`docs/domain-model.md` § Human Review).

## 5. Timeout and fallback behavior

If a case requires human approval and no reviewer acts within a configured window, the system
must not default to executing the action. Safe fallback is to keep the account/customer
protected (i.e., stay in the more conservative state) and escalate further (e.g., notify a
supervisor queue) — never silently expire into automatic approval. Timeout duration itself is
`TBD` pending an operational SLA decision.

## 6. Review queues

`OPEN QUESTION` / `PLANNED`: queue prioritization (e.g., by risk, by amount, by SLA breach
risk) is not designed yet — will be defined alongside the analyst UI in Phase 10 of
`docs/implementation-roadmap.md`.

## 7. Audit trail

Every human decision is an Audit Event (`docs/observability.md` § Audit Log) in addition to
being stored as a `Human Review` record — this makes "what did the human actually see and
decide, and when" independently reconstructable from the audit log even if the case record is
later modified.
