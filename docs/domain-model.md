# Domain Model

Owns: domain concepts and their relationships. See `docs/data-dictionary.md` for the
underlying LATAM Bank dataset schema these entities are derived from, and `docs/
decision-policy.md` for how these concepts move through the decision pipeline.

## 1. Why this document exists

The system must never collapse "what happened, what we know, what we suspect, and what was
decided" into a single `fraud_score` (`prompt.md` § 60). This document defines the vocabulary
that keeps those concepts distinct throughout the code, the UI, and the audit trail.

## 2. Epistemic categories (used everywhere below)

| Category | Definition | Example |
|---|---|---|
| **Fact** | Directly established by an authoritative source (a system of record) | "Transaction T123 posted at 14:02 for $850 USD" (from `transactions`) |
| **Evidence** | Information relevant to evaluating a hypothesis; may be weak or contradicted | "Device D9 was first seen today" |
| **Hypothesis** | A possible explanation not yet established as fact | "This transaction was made by someone other than the customer" |
| **Unknown** | Information that is unavailable or insufficient | "We don't know whether the customer's phone was with them" |
| **Model prediction** | Output of an ML model, with a version | `fraud_risk_score = 0.82 (model v1.3)` |
| **Policy decision** | A deterministic business/operational authorization outcome | "This action is eligible for automation under Policy v2.1" |
| **Human decision** | A decision made or approved by an authorized human | "Analyst A. Torres approved the dispute" |

Every field, UI element, and log entry that represents one of these must be labeled as such —
never presented in a way that implies a hypothesis is a fact, or a policy decision is a human
decision.

## 3. Core entities

Entities map onto the LATAM Bank dataset (`docs/data-dictionary.md`) where noted; entities
introduced by this system (not present in the raw dataset) are marked **[new]**.

### Customer
From `customers`. Do not use unnecessary PII (`prompt.md` § 9): the investigation flow needs
`customer_id`, `segment`, `country`, `customer_status`, account age (derived from
`registration_date`), and authentication level **[new]** — not full name/address/document
number for routine risk assessment. Full PII is retrieved only when an analyst or a specific
verified step needs it, and that access is itself audited (`docs/security-model.md`).

### Account / Product
From `products`. A customer's checking account, credit card, etc. — the thing a transaction
happens against. `product_status`, `current_balance`, `credit_limit`, `opening_channel` feed
risk features.

### Card / Device
`Device` is **[new]** relative to the dataset — it must be derived from `digital_events`
(`session_id`, `platform`, `browser`, `ip_address`/`ip_country`) since the dataset has no
standalone device table. Fields: `device_id` (derived/synthesized), `first_seen`, `last_seen`,
`customer_count` (how many customers have used it), `known_customer` (has this device been
seen for this customer before), `risk_score` **[model output, not fact]**.

### Transaction
From `transactions`. `transaction_id`, `amount`/`amount_usd`, `currency`, `channel`,
`merchant_name`/`merchant_category`, `transaction_country`, `transaction_status`,
`authorization_result` (`response_code`/`transaction_status`), `card_present` (not directly
present — derive from `channel`; document as a derived/approximate field). The dataset's own
`is_fraud` and `fraud_score` on this table are **synthetic datathon labels**, not this
system's ground truth or model output — see `docs/data-lineage.md` § Leakage for why they are
excluded from model features and used only (if at all) as an evaluation reference with that
caveat stated every time.

### Merchant
Derived from `transactions.merchant_name` / `merchant_category` — the dataset has no separate
merchant dimension table. `merchant_id` **[new, synthesized from merchant_name]**,
`historical_chargeback_rate` **[new, derived from complaint/transaction history]**.

### Customer Interaction
From `call_center_interactions` and `call_transcripts` (for voice/chat) — the customer's
statement that starts an investigation. `interaction_id`, `channel`, `contact_reason`,
transcript text, `detected_sentiment`. In the AI-first flow, an interaction may instead
originate from a chat message rather than a call — model both the same way.

### Fraud/Dispute Case **[new]**
The central case object created when an interaction triggers an investigation. Fields:
`case_id`, `customer_id`, `transaction_id`, `created_at`, `status`, `risk_score` (from the
model — clearly a model prediction, not the case's final field for "fraud" or "legitimate"),
`decision`, `decision_reason`, `escalation_required`, `human_review_status`.

### Evidence **[new]**
`evidence_id`, `case_id`, `source` (which table/tool it came from), `type`, `value`,
`direction` (`supports_fraud` | `supports_legitimate` | `neutral`), `confidence`, `timestamp`,
`provenance` (exact query/tool call that produced it). Every evidence item must be traceable
back to a fact or a specific model output — never to "the LLM said so."

### Evidence Graph **[new]**
A graph rooted at the Customer, with edges to Devices, the disputed Transaction, and related
signals (merchant, recent transactions, complaints), where each node/edge carries evidence,
direction, confidence, and timestamp. See the example in `prompt.md` § 10. The graph must be
able to answer: what do we know, what don't we know, what supports fraud, what supports
legitimacy, what contradicts other evidence, how recent is each signal, and where did it come
from.

### Decision **[new]**
`decision_id`, `case_id`, `decision`, `model_version`, `policy_version`, `prompt_version`,
`evidence_ids`, `confidence`, `explanation`, `created_at`. This is the AI/policy-engine output
— distinct from the Human Review record below even when a human simply approves it unchanged.

### Human Review **[new]**
A record of a human's decision on an escalated or approval-required case: reviewer identity,
timestamp, the case/decision it responds to, the reviewer's action (approve / reject / modify
/ request more evidence), and any override rationale. Never merged into the `Decision` record
— keeping them distinct is what makes "AI recommended X, human decided Y" auditable.

### Audit Event **[new]**
Immutable-style log entry for every state transition and tool execution
(`docs/observability.md` § Audit Log for the exact shape and redaction rules).

### Decision Provenance **[new, cross-cutting]**
Not a table — a required property of every Decision and Human Review: it must be possible to
answer what data was used, which snapshot, which feature/model/policy/prompt version, what
evidence supported and contradicted the outcome, who (or what) decided, and what action
resulted (`docs/decision-policy.md` § Decision Provenance owns the full chain).

## 4. Uncertainty as a first-class concept

Represent, not suppress, uncertainty: `unknown`, `insufficient_evidence`,
`conflicting_evidence`, `unavailable_data`, `stale_data`, `low_confidence_model_output`,
`unsupported_hypothesis`. Where useful, an uncertainty record carries: source, type,
confidence, missing information, contradictions, the decision it affects, its impact, and a
timestamp. The system must never force a `fraud` / `legitimate` label when the evidence graph
doesn't support one — the valid outputs of an investigation include "insufficient evidence,
ask a question" and "insufficient evidence, escalate."

## 5. What this model deliberately avoids

A single `fraud_score` field standing in for "the decision." A model prediction being written
directly into a customer-facing explanation without passing through the Decision/Evidence
layers. A human's approval being indistinguishable from the AI's original recommendation in
the audit trail.
