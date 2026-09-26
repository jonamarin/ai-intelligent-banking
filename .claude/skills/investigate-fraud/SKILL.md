---
description: Workflow for reasoning through a fraud/dispute investigation case (real or a test scenario) the way the system's Evidence Engine and Decision Engine should. Use when asked to investigate a specific case, reason about a golden case, or design/debug the evidence-graph and decision logic.
---

# Investigate Fraud

Mirrors the pipeline in `docs/architecture.md` § 2 and the epistemic categories in
`docs/domain-model.md` § 2. Follow this order — do not jump to a conclusion before working
through the evidence.

1. **Collect facts.** What does an authoritative source (the dataset/system of record) directly
   establish about this transaction, customer, device, and merchant?
   (`docs/domain-model.md` § Fact)
2. **Collect evidence.** What signals are relevant to the fraud hypothesis, even if weak or
   indirect? (`docs/domain-model.md` § Evidence)
3. **Preserve provenance.** For every fact and evidence item, record its source (which table,
   tool, or model call produced it) and timestamp.
4. **Identify hypotheses.** State the candidate explanations explicitly (e.g., "unauthorized
   third party," "customer forgot a legitimate purchase," "merchant-side error") — do not
   silently collapse this to a single score.
5. **Identify supporting evidence** for each hypothesis.
6. **Identify contradictory evidence** — evidence against each hypothesis, including evidence
   that contradicts other evidence (`docs/domain-model.md` § Evidence Graph).
7. **Identify missing information** — what would materially change the assessment if known,
   and is it worth asking for (`docs/architecture.md` § 8, Next-Best-Question)?
8. **Evaluate model outputs** as model predictions, not facts — cite `model_version` and
   treat the score as one input, not the conclusion (`docs/domain-model.md` § Model
   prediction).
9. **Apply deterministic policy** — action-risk classification and risk-band logic from
   `docs/decision-policy.md` §§ 5–6. This step is not a judgment call; it's a lookup against
   documented (if `PROPOSED`) rules.
10. **Represent uncertainty** explicitly wherever evidence is insufficient or conflicting —
    valid outputs include "insufficient evidence, ask a question" and "insufficient evidence,
    escalate," not a forced binary label (`docs/domain-model.md` § 4).
11. **Recommend next action**, labeled clearly as a recommendation, not a decision
    (`docs/domain-model.md` § Decision vs. Human Decision).
12. **Escalate when required** — per the approval matrix in `docs/human-oversight.md` § 2 and
    the action-risk table in `docs/decision-policy.md` § 6, not based on how confident the
    reasoning feels.

## Prohibited

- Unsupported fraud conclusions — every conclusion traces to cited evidence.
- Fabricated evidence — never invent a signal that wasn't actually retrieved.
- Treating model or LLM confidence as authorization for any action
  (`docs/decision-policy.md` § 2).
- Recommending or simulating an irreversible financial action being executed by the LLM
  without going through the human-approval gate the action's risk level requires
  (`docs/human-oversight.md` § 2).

## When working with the dataset

Never use `transactions.fraud_score` or `is_fraud` as an input to the reasoning itself — they
are synthetic dataset labels, not signals a real investigation would have had
(`docs/data-lineage.md` § 5). They may only be referenced, clearly labeled `SYNTHETIC`, when
evaluating how a completed investigation's conclusion compares to the dataset's label.
