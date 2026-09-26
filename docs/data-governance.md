# Data Governance

Owns: data-use rules and ownership. See `docs/data-lineage.md` for how data actually moves and
transforms, and `docs/security-model.md` for the threat model this governs against.

## 1. Data classification

| Class | Examples in this dataset | Handling |
|---|---|---|
| Direct identifiers | `document_number`, `email`, `mobile_phone`, `address` (`customers`) | Never sent to the LLM unless the specific step requires it; masked in logs; access audited |
| Quasi-identifiers | `date_of_birth`, `postal_code`, `city` + `country` combination | Minimize combination exposure; avoid combining more than needed for a given feature/decision |
| Financial data | `amount`, `current_balance`, `credit_limit`, transaction detail | Core to the workflow; still redacted in logs/traces per `docs/observability.md` § 2 |
| Sensitive derived signals | `detected_accent`, `credit_score`, `estimated_monthly_income` | Usable for evaluation slicing (`docs/model-evaluation.md` § 13); never used as a decision input without an explicit, documented justification |
| Free text | call transcripts, complaint `description`, survey `open_comments` | Untrusted input (`docs/security-model.md` § 1); may contain incidental PII the customer volunteered — treat as sensitive by default |
| Synthetic | the entire dataset | Labeled `SYNTHETIC` everywhere it's used; never presented as real customer data |

## 2. Data minimization and purpose limitation

Retrieve only the fields a given step needs (`docs/domain-model.md` § Customer — e.g., routine
risk scoring needs `segment`/`country`/`customer_status`, not `document_number`). A tool that
retrieves customer data returns a purpose-scoped view, not the full row, by default.

## 3. Access control

Access to customer data is mediated by the tool/service layer, never direct database access
from the LLM or orchestration prompt (`docs/architecture.md` § 14). Role-based scoping (RBAC)
for internal roles is `PLANNED` per `docs/security-model.md` § 3.

## 4. Retention and deletion

`TBD` / `OPEN QUESTION`: no retention or deletion policy has been approved. For this
prototype, all data is synthetic, so retention risk is low, but the design should not assume
that — implement retention/deletion as a configurable policy from the start rather than
hardcoding "keep forever," since a real deployment would need it. Audit logs likely need
longer retention than application logs; exact periods are a compliance decision this project
does not make unilaterally.

## 5. PII, financial data, sensitive attributes

See § 1. Sensitive attributes (`detected_accent`, `country`, `segment`) are explicitly
excluded from being used as fraud-decision inputs — they may only be used for fairness
evaluation slicing (`docs/model-evaluation.md` § 13), never as model features or policy
conditions, to avoid encoding discriminatory proxies into automated decisions.

## 6. Synthetic and anonymized data, evaluation datasets

The LATAM Bank dataset is entirely synthetic (`docs/data-lineage.md` § Source). Evaluation
fixtures in `evaluation/golden_cases/` are hand-authored synthetic scenarios, not sampled real
cases. No anonymization pipeline is needed because no real data enters this project — if that
ever changes, this document must be revisited before any real data is used.

## 7. Training restrictions

Do not train on `fraud_score` (leakage — `docs/model-evaluation.md` § 3) or on any field that
wouldn't have been available at decision time. Do not train on free-text fields containing
unredacted PII without a documented redaction step first.

## 8. Redaction

Mechanism owned by `docs/observability.md` § 2 (logs/traces) and applied equally before any
data reaches LLM context that doesn't need the raw value.

## 9. Data quality

See `docs/data-lineage.md` § Data Quality for the LATAM Bank dataset's documented quality
characteristics (2% duplicates, 5% nulls, late arrivals, schema evolution) and how the
ingestion pipeline must handle them; this document's rule is simply that data-quality
validation is not optional given those documented characteristics.

## 10. Data ownership

Within this project, `docs/` document owners (per `CLAUDE.md` § 11) own the rules; the LATAM
Bank dataset itself is owned/published by the Factored Datathon organizers, not this project —
this project only consumes it under the competition's data-use terms
(`project_presentation.txt` § Data and execution boundaries).

## 11. Jurisdiction considerations

The dataset spans three jurisdictions (Mexico, Colombia, Argentina) with distinct data-
protection regimes. `OPEN QUESTION`: no jurisdiction-specific compliance analysis has been
done for this prototype — flag this explicitly in the final report rather than implying
compliance. `Requires legal/compliance validation.`

## 12. Legal/compliance review requirement

Nothing in this repository constitutes a compliance determination. Any claim of regulatory
compliance requires authoritative legal review this project has not obtained — use
`Requires legal/compliance validation.` wherever the topic comes up instead of asserting
compliance.
