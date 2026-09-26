# Product Requirements

Owns: what the product must accomplish. See `docs/architecture.md` for how, `docs/
decision-policy.md` for the automation/authorization logic, `docs/project-status.md` for what
exists today.

## 1. Business problem

Banks receive high volumes of interactions about unauthorized transactions, suspicious card
activity, duplicate charges, and disputes. Traditional rules-heavy fraud systems over-alert:
unnecessary card blocks, customer friction, high human-agent workload, slow investigation, and
inconsistent decisions (`prompt.md` § 1). The goal is stated as **"Catch More. Flag Less."** —
detect genuine fraud while minimizing unnecessary intervention on legitimate customers.

## 2. Customer problem

A customer sees a transaction they don't recognize and needs a fast, low-friction answer:
"is this fraud, and what happens next?" Excessive re-authentication, redundant questions, or a
premature card freeze on a legitimate transaction are as much a failure as missing real fraud.

## 3. Chosen workflow

Per the competition brief (`project_presentation.txt`), teams choose one coherent workflow and
solve it deeply rather than spreading thin. This project chooses:

> **Transaction-dispute intake and fraud investigation** — a customer reports an unrecognized
> or suspicious transaction; the system authenticates them, reconstructs the transaction and
> its context, builds an evidence graph, applies a fraud/risk model and deterministic policy,
> and resolves, asks a clarifying question, or escalates to a human.

This is the workflow `prompt.md` specifies in full (§ 2–22) and it maps directly onto the
`complaints` (PQR) and `transactions` tables in the LATAM Bank dataset
(`docs/data-dictionary.md`). Card support, account changes, and credit eligibility are
explicitly out of scope (`project_presentation.txt` — "these are examples, not separate
tracks"; depth beats breadth).

## 4. Users

- **Customers** (retail banking customers in Mexico, Colombia, Argentina) — report the
  problem, answer clarifying questions, receive a plain-language explanation and outcome.
- **Fraud/dispute analysts** (`service_agents` in the dataset) — receive escalated cases with a
  structured evidence packet, approve/reject high-impact actions.
- **System administrators / engineers** — operate, monitor, and evolve the system.

Operational users are internal; there is no executive/business-owner persona with direct
product requirements beyond the executive dashboard described in `prompt.md` § 35.

## 5. Primary use cases

1. Customer reports an unrecognized transaction → system investigates and resolves it
   automatically when policy allows (Scenario A, `docs/demo-script.md`).
2. Customer reports a transaction with strong fraud indicators → system protects the account
   and creates a dispute/escalation per policy (Scenario B).
3. Ambiguous case with mixed evidence → system asks one targeted clarifying question or
   escalates rather than guessing (Scenario C).
4. High-value or irreversible action is implicated → mandatory human approval regardless of AI
   confidence (Scenario D).
5. A dependency (LLM, model, database) is unavailable → system degrades safely instead of
   failing open or hanging (`docs/architecture.md` § Failure Modes).

## 6. Secondary use cases

- Analyst reviews a case's evidence graph and audit trail without needing to reconstruct
  context manually (`prompt.md` § 21).
- Executive views aggregate metrics (automation rate, escalation rate, estimated loss) —
  `prompt.md` § 35, built only if Phase 10 time allows; not required for the core
  demonstration.

## 7. Functional requirements

- Understand a free-text customer report in Spanish (Mexican/Colombian/Argentine variants);
  authenticate the customer before any sensitive retrieval or action.
- Retrieve the relevant transaction, customer behavioral context, device/session context
  (from `digital_events`), and merchant signals.
- Build an evidence graph distinguishing evidence for fraud, evidence for legitimacy,
  contradictions, and unknowns (`docs/domain-model.md`).
- Produce a calibrated fraud/risk score from a traditional ML model, separate from the LLM's
  narrative reasoning (`docs/model-evaluation.md`).
- Apply a deterministic, configurable policy to decide: auto-resolve, ask a targeted question,
  perform a low-risk action, create a dispute, protect the account, or escalate
  (`docs/decision-policy.md`).
- Generate two explanations — customer-facing (plain language) and analyst-facing (technical,
  with evidence and versions) (`prompt.md` § 22).
- Log a complete, versioned decision and evidence trail for every case (`docs/decision-policy.md`
  § Decision Provenance).
- Degrade safely when the LLM, fraud model, or a data dependency is unavailable
  (`docs/architecture.md` § Failure Modes).

## 8. Non-functional requirements

Privacy, explainability, fairness, reliability, scalability, reproducibility (see the
respective `docs/` owners). Meaningful support for Spanish is a hard requirement, since the
dataset and customer base are Spanish-speaking. Latency targets and scalability targets are
defined in `docs/architecture.md` § Performance and Scale (they are design targets — no load
testing has occurred; nothing here is a measured result).

## 9. Scope

In scope: dispute/fraud investigation workflow end-to-end, for Spanish-language interactions,
using the LATAM Bank dataset as the sole data source, as a prototype demonstrating production
readiness thinking (not live operation).

## 10. Non-goals

- Not a general-purpose banking chatbot (`prompt.md` § "Do NOT build a generic LLM chatbot").
- Not card support, account-change, or credit-eligibility workflows — out of scope by the
  "choose one workflow" rule, even though the dataset could support them.
- Not a live, production banking service; ten-day/hackathon-scale submission
  (`project_presentation.txt` § Scope).
- No real money movement, no live lending decisions, no production deployment.
- Not a demonstration of forecasting, streaming infrastructure, or a multi-agent tool-count
  target for their own sake — `project_presentation.txt` explicitly says these are not
  mandatory; add them only if they serve the chosen workflow.

## 11. Success metrics

`TBD` — no business-approved thresholds exist. `docs/evaluation-plan.md` defines the
categories of metrics (fraud detection, business cost, LLM safety, reliability, fairness) the
system must report; actual target values are `OPEN QUESTION` until a baseline is measured
against the dataset. Do not invent target numbers.

## 12. Assumptions

- The dataset's `is_fraud` / `fraud_score` fields on `transactions` are **synthetic
  datathon-generated labels**, not a real bank's ground truth, and `fraud_score` is treated as
  a leakage risk (it may itself be a prior model's output) rather than a usable feature — see
  `docs/data-lineage.md`.
- "Authentication" in this prototype uses a trusted test session, per the competition rule that
  "a national ID or customer number alone does not prove identity" — not a real KYC/auth
  system.
- `LLM_MODE=mock` is available and sufficient for CI, tests, and demos without a paid API key.

## 13. Language scope decision

**Decided (2026-09-25):** the brief asks for "meaningful interactions in Spanish and
Portuguese" (`project_presentation.txt` § Problem Statement), but the supplied LATAM Bank
dataset contains only Spanish-language data across Mexico, Colombia, and Argentina — no
Portuguese or Brazil content. Rather than fabricate Portuguese coverage against data that
doesn't exist, this project implements **Spanish only**, matching the dataset, and reports the
Portuguese gap explicitly as a known limitation in the README and final report
(`docs/project-status.md` § Known limitations). This is a data limitation being handled
honestly, not an oversight — do not revisit this without a corresponding change to the
underlying dataset.

## 14. Open questions

- `OPEN QUESTION`: Whether an executive dashboard (`prompt.md` § 35) is built at all, given
  "implementing more workflows/features does not earn an automatic bonus" — depth on the core
  investigation flow should be prioritized first.

## 15. Dependencies

Depends on the LATAM Bank dataset being available locally (raw files are not present in this
repository as of this writing — `docs/data-lineage.md` § Source documents the expected
ingestion path once the dataset files are added).

## 16. Constraints

Only organizer-approved data and permitted external resources
(`project_presentation.txt` § Data and execution boundaries). No private customer records,
credentials, or restricted data in the repository or in any external model request.
