---
description: Security review checklist for this repository — authentication, authorization, PII, secrets, prompt injection, tool access, auditability, and more. Use before completing any change touching authentication, authorization, PII, financial actions, tools, or infrastructure, or when explicitly asked for a security review.
---

# Review Security

Review the change (or the relevant existing code, if reviewing broadly) against each area
below. This mirrors `docs/security-model.md` § 2 and `docs/guardrails.md` — read those first
if this is the first security review in the session.

## Areas to review

- **Authentication:** is identity established deterministically (not inferred from
  conversation content)? (`docs/security-model.md` § 3)
- **Authorization:** is every action scoped to what the authenticated identity is actually
  allowed to do — never trusting a client-supplied role/customer_id?
  (`.claude/rules/security.md`)
- **PII:** is only the minimum necessary PII retrieved/logged/sent to the LLM?
  (`docs/data-governance.md` § 1–2)
- **Secrets:** any hardcoded secret, credential, or key — in code, config, comments, or test
  fixtures?
- **Prompt injection:** is customer/RAG content structurally separated from instructions? Does
  any code path let conversational content change authorization or tool permissions?
  (`docs/security-model.md` § 2, `docs/guardrails.md` § 4)
- **Tool access / tool authorization:** does every tool call pass the full chain in
  `docs/architecture.md` § 6 — authentication, eligibility, evidence sufficiency, policy,
  human-approval check — before executing? Is there any path that calls a tool's underlying
  implementation directly, bypassing the policy engine?
- **Auditability:** does every state-changing action produce an audit event with enough
  provenance to reconstruct the decision (`docs/decision-policy.md` § 9)?
- **Idempotency:** does every state-changing action have an idempotency key, and is it
  actually enforced (not just documented)? (`docs/architecture.md` § 11)
- **Validation:** is every external input (API request, tool output, LLM structured output)
  schema-validated before use?
- **Unsafe defaults:** does anything default to allow/enabled/unrestricted when it should
  default to deny/disabled/scoped?
- **High-impact automation:** does anything let an LLM's confidence or recommendation
  substitute for a required human approval or policy check? (`docs/decision-policy.md` § 2)
- **Privilege escalation:** can a lower-privileged actor (customer session, low-trust tool
  output) reach a higher-privileged action through any indirect path?
- **Data leakage:** could any response, log, trace, or explanation leak PII, secrets, or raw
  card/account numbers? (`docs/observability.md` § 2)
- **Logging:** does logging follow the redaction rules, and is nothing sensitive logged that
  shouldn't be? (`docs/observability.md` § 2)

## Output

Findings must include: severity, file/component, evidence (the actual code/line, not a
guess), impact, and remediation. Do not invent vulnerabilities that aren't actually present in
the code being reviewed — a finding needs a concrete failure scenario, not a hypothetical
"this could theoretically be a problem somewhere."

Do not weaken a security control to resolve a finding faster — fix the underlying issue. If a
finding can't be fixed within the scope of the current change, report it explicitly rather than
silently deferring it.
