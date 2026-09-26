# Backend Rules

Applies to: `src/api/`, `src/orchestration/`, `src/tools/`, `src/policies/`, `src/config/` once
they exist (`docs/architecture.md` § 4). See `docs/api-contracts.md` for the endpoint contract
and `.claude/rules/ai-agents.md` for orchestration-specific rules.

- Validate every API input with a Pydantic schema; never trust client-provided data,
  including client-provided authorization claims (role, customer_id) — derive authorization
  from the authenticated session/context, not from request body fields.
- Keep domain boundaries: API layer, orchestration layer, tool layer, and data-access layer
  are separate modules with typed interfaces between them — no layer reaches past the one
  directly below it (e.g., the API layer never touches SQLAlchemy models directly).
- Dependency injection for anything that needs to be swapped in tests (LLM client, DB session,
  clock) — no hidden global state.
- Every external call (DB, LLM, tool, HTTP) has an explicit timeout and a bounded retry policy
  with backoff (`docs/architecture.md` § 10).
- Every state-changing operation is idempotent via an explicit idempotency key
  (`docs/architecture.md` § 11) — do not rely on "the client won't retry."
- Structured logging only (no bare `print`/string-concatenated logs); every log line
  correlatable by `case_id`/correlation ID (`docs/observability.md` § 1).
- Raise meaningful, typed exceptions; do not swallow exceptions to "make it work" — a caught
  exception either handles the failure per `docs/architecture.md` § 10's fallback table or
  re-raises.
- Configuration lives in `src/config/`, sourced from environment variables with `.env.example`
  documenting every key — never a hardcoded secret or environment-specific value in code.
- No giant files or giant functions; if a function is doing API validation, business logic,
  and persistence, split it.
- Write code to be testable: pure functions where possible, side effects isolated at the edges.
