"""Deterministic policy engine: risk bands, action-risk classification, tool
authorization (docs/decision-policy.md, docs/guardrails.md § 3). This is the
highest-scrutiny code in the project (docs/implementation-roadmap.md Phase 7).

- `action_risk.py` — the fixed action-risk classification table, keyed by
  tool and by transaction/requested-action facts, never by LLM output.
- `config.py` — configurable, explicitly `PROPOSED` thresholds
  (docs/decision-policy.md § 10) — never a hardcoded business number.
- `authorization.py` — the tool-authorization chain itself
  (docs/guardrails.md § 3): authenticated? case eligible? sufficient
  evidence? then classify risk, decide automation, decide human approval.
- `gateway.py` — persists a real Decision (+ AuditEvent, + HumanReview once a
  human acts) for a live, DB-backed case; golden cases stay fully offline and
  call `authorization.authorize()` directly.
"""
