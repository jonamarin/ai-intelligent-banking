"""PII redaction, prompt-injection defenses, auth/authorization helpers
(docs/security-model.md).

- `redaction.py` — the shared redaction layer (Phase 8): `mask_card_like()`
  (matches docs/observability.md § 2's exact `****1111` example) and
  `redact_value()` (recursive dict/list redaction for AuditEvent payloads).
  `src/config/logging.py`'s log-line filter (Phase 1) now imports from here
  too — one implementation, not two.

Red-team/adversarial tests for docs/guardrails.md § 4 live in
`tests/security/` (Phase 8), not in this package — they exercise the
orchestration/policy code, they don't add new production code of their own.
"""
