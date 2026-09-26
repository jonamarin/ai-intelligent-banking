# Decision Policy

Owns: how an AI recommendation becomes an authorized action. See `docs/human-oversight.md` for
the approval matrix and escalation mechanics, `docs/guardrails.md` for how each stage below is
actually enforced in code, and `docs/domain-model.md` for the entity definitions used here.

## 1. The conceptual flow

```
Risk Assessment
      ↓
Evidence Sufficiency
      ↓
Action Risk
      ↓
Policy Eligibility
      ↓
Is Automation Allowed?
      ↓
Is Human Approval Required?
      ↓
Execute Authorized Action
      ↓
Audit Result
```

(`prompt.md` § 14.) Each arrow is a deterministic check, not an LLM judgment call.

## 2. The four inequalities that must always hold

> **AI recommendation != authorization**
> **AI confidence != permission**
> **Fraud probability != final decision**
> **Policy eligibility != execution authorization**

These are enforced in code (`docs/guardrails.md` § Enforcement Layers), not just documented.
An LLM proposing `freeze_card(customer_id)` produces a **proposal record**; only the policy
engine's authorization check produces an **execution**.

## 3. Risk assessment

Input: the ML fraud/risk model's calibrated score (`docs/model-evaluation.md`) plus evidence-
graph signals (novel device, novel country, failed authentication, amount deviation, etc. —
`docs/domain-model.md` § Evidence Graph). Output: a risk value with a model version, not a
decision.

## 4. Evidence sufficiency

Before any risk band below is applied, the Decision Engine must check whether the evidence
graph actually supports a confident answer. Insufficient or conflicting evidence routes to
"ask a targeted question" (§ 7) or escalation — **never** to a forced automatic decision.

## 5. Risk bands (illustrative structure, not approved thresholds)

```
LOW RISK:       risk < 0.30           → eligible for automatic resolution, if policy allows
MEDIUM RISK:    0.30 <= risk < 0.70   → collect additional evidence / ask a question
HIGH RISK:      0.70 <= risk < 0.90   → protect account + possible dispute + review per action risk
CRITICAL:       risk >= 0.90          → high-risk workflow, human review
```

These numbers are illustrative structure carried over from `prompt.md` § 14, **not**
business-approved thresholds — they are `PROPOSED` and must be configurable, not hard-coded
(`prompt.md`: "These thresholds must NOT be blindly hard-coded"). The final action depends on
risk **and** transaction amount, customer authentication state, policy, action reversibility,
uncertainty, and data quality — never on risk alone.

## 6. Action risk levels

| Level | Examples | Automation |
|---|---|---|
| Low | Explain transaction, show status, retrieve information, summarize case | Can be automated |
| Medium | Create dispute, request additional authentication, notify customer, create fraud case | Automate only under explicit policy |
| High | Freeze card, large refund, account restriction, other high-value action | Requires stronger authorization |
| Irreversible / critical | Account closure, large transfer, beneficiary change, major financial adjustment | Deterministic controls + human approval required |

(`prompt.md` § 15.) The action-risk level is looked up from a fixed classification table in
code — the LLM cannot talk its way into a lower action-risk classification for a given action
type.

## 7. Next-Best-Question gate

Before asking the customer anything, compute expected information gain (expected reduction in
decision uncertainty) against expected customer friction (`docs/architecture.md` § 8). Ask
only if the gain clears a configured threshold; otherwise proceed with what's known or
escalate. This keeps "ask a question" from becoming a way to avoid making a real decision.

## 8. Human escalation as a decision outcome

Escalation is a first-class, policy-driven outcome — not a fallback used only on failure. When
triggered, generate a structured case packet (`docs/human-oversight.md` § Case Packet) so the
analyst never reconstructs the case manually.

## 9. Decision provenance

Every Decision record (`docs/domain-model.md` § Decision) must capture, and every audit query
must be able to answer:

```
Input → Data Snapshot → Feature Version → Model Version → Model Output
      → Evidence → Policy Version → LLM Recommendation → Human Decision → Action
```

Concretely: what data was used, when/which snapshot, which feature version, which model
version, what the model output, what evidence supported/contradicted the result, which policy
version applied, what the LLM recommended, what the human decided, who approved it, which
action executed, when, and what the result was (`prompt.md` § 19, § 54). A decision must be
reproducible from this trail whenever technically feasible (`docs/model-evaluation.md` §
Versioning and Rollback).

## 10. Business vs. technical decisions

Keep these distinct in code and documentation:

- **Business decision** (example): "Refunds above a certain amount require human approval."
  This is a policy-owner call, not something this repository invents a number for.
- **Technical implementation** (example): "The policy engine reads the configured refund
  threshold and compares it to the transaction amount." This repository implements the
  mechanism; it does not manufacture the business number.

Do not invent business thresholds, and do not let a technical default quietly become a de
facto business policy without labeling it `PROPOSED`.

## 11. What this document does not own

Which actions specifically require a human vs. can be automated, and the escalation/timeout
mechanics themselves, are owned by `docs/human-oversight.md`. Runtime enforcement mechanics
(structured-output validation, tool permission checks, loop/cost limits) are owned by
`docs/guardrails.md`.
