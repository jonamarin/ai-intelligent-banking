# API Contracts

Owns: system/API/event boundaries. See `docs/architecture.md` § 6 for the tool-authorization
flow these endpoints ultimately gate, and `docs/security-model.md` for the trust model.

**Status: only `/api/v1/health` is implemented (Phase 1, `docs/project-status.md`); everything
else below is `PROPOSED`.** This document defines the intended contract so implementation
doesn't have to re-derive it from `prompt.md`.

## 1. Endpoints

| Method & path | Purpose | Status |
|---|---|---|
| `GET /api/v1/health` | Liveness/readiness | **IMPLEMENTED** (`src/api/main.py`) |
| `POST /api/v1/cases` | Create a case from a customer interaction | PROPOSED |
| `POST /api/v1/cases/{case_id}/messages` | Add a customer/agent message to a case | PROPOSED |
| `GET /api/v1/cases/{case_id}` | Retrieve case state | PROPOSED |
| `GET /api/v1/cases/{case_id}/evidence` | Retrieve the evidence graph | PROPOSED |
| `GET /api/v1/cases/{case_id}/decision` | Retrieve the current decision + provenance | PROPOSED |
| `POST /api/v1/cases/{case_id}/approve` | Human approval of a pending action | PROPOSED |
| `POST /api/v1/cases/{case_id}/reject` | Human rejection of a pending action | PROPOSED |
| `POST /api/v1/evaluate` | Trigger an evaluation run | PROPOSED |
| `GET /api/v1/metrics` | Metrics endpoint (Prometheus-compatible) | PROPOSED |

The implemented `/health` endpoint also already demonstrates two of the cross-cutting
requirements below ahead of the rest of the API: correlation-ID propagation (§ 2) and
structured, stack-trace-free error responses (§ 2) — see `src/api/errors.py`.

(`prompt.md` § 43.) All request/response bodies are Pydantic-validated once implemented; no
endpoint accepts unvalidated input.

## 2. Cross-cutting requirements

- **Authentication:** every endpoint except `/health` requires an authenticated session
  context (`docs/security-model.md` § 3). Mechanism `TBD`.
- **Authorization:** role-scoped — a customer session can only read/act on their own cases; an
  analyst session can read/act within their assignment scope; `approve`/`reject` require an
  analyst or supervisor role, never a customer session.
- **Correlation IDs:** every request carries/generates a correlation ID propagated through
  traces and audit events (`docs/observability.md` § 1).
- **Idempotency:** `POST /cases/{case_id}/approve` and `/reject` (and any future action
  endpoint) require an idempotency key so a retried request cannot double-execute
  (`docs/architecture.md` § 11).
- **Versioning:** `/api/v1/` prefix reserves room for a future `/v2/`; breaking changes get a
  new version, not a silent contract change.
- **Request validation:** reject malformed/out-of-range input with a structured 4xx error
  before it reaches any business logic.
- **Response schemas:** typed and documented per endpoint once implemented (OpenAPI, generated
  from FastAPI/Pydantic — no hand-maintained duplicate schema doc).
- **Errors:** structured error responses (`{"error": {"code", "message", "correlation_id"}}`
  shape, `TBD` exact schema); internal stack traces are never exposed to the client
  (`prompt.md` § 44).
- **Retries:** client-safe retry guidance documented per endpoint once implemented (only
  idempotent operations are safe to retry blindly).
- **Audit:** every state-changing call produces an audit event (`docs/observability.md` § 3).
- **Rate limiting:** `PLANNED` at the API gateway layer — not implemented yet.

## 3. Event contracts (proposed, introduced only when a phase needs asynchronous processing)

Candidate topics, if/when an event system is introduced (`docs/architecture.md` § 7):
`customer-interactions`, `transactions`, `fraud-signals`, `cases`, `decisions`, `actions`,
`audit-events` (`prompt.md` § 46). Consumer processing must be idempotent; retry and
dead-letter behavior required before any consumer is considered production-viable. No event
schema is defined yet — `PLANNED`.

## 4. Security of APIs

See `docs/security-model.md` §§ 3–4 for the authentication/authorization model these contracts
depend on. This document does not restate it.
