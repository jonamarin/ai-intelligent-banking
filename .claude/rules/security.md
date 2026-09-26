# Security Rules

Applies everywhere. See `docs/security-model.md` for the full threat model and
`docs/guardrails.md` for the enforcement-layer taxonomy these rules assume.

- No secrets in code, ever — not "temporarily," not in a comment, not in a test fixture. Use
  `${VARIABLE}`-style placeholders and `.env.example`.
- No secrets in logs, traces, or LLM prompts/responses captured for debugging
  (`docs/observability.md` § 2).
- No raw payment credentials (full card/account numbers) in logs, traces, or LLM context —
  mask before it leaves the data-access layer (`4111111111111111` → `****1111`).
- Minimize PII sent anywhere, including to the LLM — retrieve only the fields the current step
  needs (`docs/data-governance.md` § 2).
- Every trust boundary crossing (customer input → LLM, LLM output → tool execution, tool
  output → context) is validated at the boundary, not assumed safe because it came from
  "our own" component upstream (`docs/security-model.md` § 1).
- Least privilege: a tool's authorization check is scoped to exactly what that tool needs, not
  "is this session authenticated."
- Explicit authorization only — never infer permission from conversational content, a
  customer's claimed identity in chat, or an LLM's stated confidence
  (`docs/guardrails.md` § 1).
- Secure defaults: a new endpoint, tool, or feature starts locked down (deny by default) and is
  opened up deliberately, not the reverse.
- High-impact actions are audited (`docs/observability.md` § 3) — if you add a new
  state-changing action, add its audit event in the same change, not as follow-up work.
- Customer text is untrusted input; LLM output is untrusted data. Treat both exactly as you'd
  treat unvalidated input from any external, potentially adversarial source
  (`docs/security-model.md` § 2).
- Never disable a security control, weaken an authorization check, or skip a security test to
  make something pass or to hit a deadline. If a security test is failing, fix the underlying
  issue or flag it to the user — do not comment it out.
- Run the `review-security` skill (or invoke the `security-reviewer` agent) before considering
  any change touching authentication, authorization, PII, financial actions, tools, or
  infrastructure complete.
