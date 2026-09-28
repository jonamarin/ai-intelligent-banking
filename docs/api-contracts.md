# API Contracts

Owns: system/API/event boundaries. See `docs/architecture.md` § 6 for the tool-authorization
flow these endpoints ultimately gate, and `docs/security-model.md` for the trust model.

**Status: Phase 10 implements the core case endpoints (`src/api/cases.py`); Phase 13 adds
`GET /metrics`. `/messages` and `/evaluate` remain `PROPOSED`.** This document defines the
intended contract so implementation doesn't have to re-derive it from `prompt.md`.

## 1. Endpoints

| Method & path | Purpose | Status |
|---|---|---|
| `GET /api/v1/health` | Liveness/readiness | **IMPLEMENTED** (`src/api/main.py`, Phase 1) |
| `POST /api/v1/cases` | Build the evidence graph for a transaction, run it through orchestration, persist the Decision | **IMPLEMENTED** (`src/api/cases.py`, Phase 10) |
| `GET /api/v1/cases` | List recent cases (the analyst review queue) | **IMPLEMENTED** — analyst/supervisor role only |
| `GET /api/v1/cases/{case_id}` | Retrieve case state | **IMPLEMENTED** — role-shaped: a customer session gets status + plain-language explanation only; an analyst/supervisor session also gets the evidence graph, decision provenance, and audit trail. **Deviates from this table's original proposed shape**: evidence and decision are returned inline here rather than via the two separate sub-resource endpoints originally proposed below, to render one analyst page in one request; see `src/api/README.md` for the reasoning |
| `POST /api/v1/cases/{case_id}/messages` | Add a customer/agent message to a case | PROPOSED — no live conversational intake channel exists yet (`docs/project-status.md` § Phase 6 detail: `customer_message` for a live case is sourced from `call_transcripts`, not typed in real time) |
| `GET /api/v1/cases/{case_id}/evidence` | Retrieve the evidence graph | Folded into `GET /cases/{case_id}`'s analyst view instead of a separate endpoint (see above) |
| `GET /api/v1/cases/{case_id}/decision` | Retrieve the current decision + provenance | Folded into `GET /cases/{case_id}`'s analyst view instead of a separate endpoint (see above) |
| `POST /api/v1/cases/{case_id}/approve` | Human approval of a pending action | **IMPLEMENTED as `POST /cases/{case_id}/review`** with `{"action": "approve"}` — one handler for both approve/reject rather than two near-duplicates, idempotency-key-protected (`src/policies/gateway.py`) |
| `POST /api/v1/cases/{case_id}/reject` | Human rejection of a pending action | **IMPLEMENTED as `POST /cases/{case_id}/review`** with `{"action": "reject"}` — see above |
| `POST /api/v1/cases/session` | Set the trusted-test-identity role cookie (`src/api/deps.py`) | **IMPLEMENTED**, Phase 10 addition not in the original proposed table — no real auth system exists (`docs/security-model.md` § 3), so this stands in for it, honestly labeled everywhere it's used |
| `POST /api/v1/evaluate` | Trigger an evaluation run | PROPOSED — `evaluation/run.py` is a CLI, not an HTTP trigger (`evaluation/README.md`) |
| `GET /metrics` | Metrics endpoint (Prometheus-compatible) | **IMPLEMENTED** (`src/api/main.py`, Phase 13) — deliberately **not** under `/api/v1/`: this follows the standard, tooling-expected Prometheus convention (`GET /metrics` at the root) rather than this project's own versioned business-API prefix, since Prometheus scrape configs assume that path by convention (`infrastructure/prometheus/prometheus.yml`) |

The implemented `/health` endpoint also already demonstrates two of the cross-cutting
requirements below ahead of the rest of the API: correlation-ID propagation (§ 2) and
structured, stack-trace-free error responses (§ 2) — see `src/api/errors.py`. The Phase 10
endpoints demonstrate two more: request validation (every body is a `extra="forbid"` Pydantic
model, `src/api/schemas.py`) and idempotency (`POST /review`, via `src/policies/gateway.py`'s
`action_executions` mechanism, Phase 9).

(`prompt.md` § 43.) All request/response bodies are Pydantic-validated once implemented; no
endpoint accepts unvalidated input.

## 2. Cross-cutting requirements

- **Authentication:** every endpoint except `/health` and `/cases` (create/list, see below)
  requires a session context — implemented as `src/api/deps.py`'s trusted-test-identity cookie
  (`docs/security-model.md` § 3: a real identity system is explicitly out of scope for this
  prototype). `POST /cases` (create) doesn't need one — a customer reporting a transaction is
  the intended entry point and carries no risk itself (`docs/decision-policy.md` § 6, Low
  action-risk); the role check gates what can be *done* with the resulting case, not whether a
  case can be opened.
- **Authorization:** role-scoped — implemented as `GET /cases/{case_id}` returning a
  role-shaped response (`CustomerCaseView` vs `AnalystCaseView`, `src/api/schemas.py`) and
  `GET /cases` / `POST /cases/{case_id}/review` requiring `require_reviewer_role`
  (analyst/supervisor only) — a customer session gets a real 403, not a hidden UI control
  (`.claude/rules/frontend.md`). **Not yet implemented**: per-customer case-ownership scoping
  ("a customer session can only read/act on their own cases") — there is no customer identity
  to scope by yet, since the trusted-test-identity abstraction has no per-customer login, only
  a role. Honestly reported, not silently claimed.
- **Correlation IDs:** every request carries/generates a correlation ID propagated through
  traces (`src/api/main.py`'s middleware, Phase 1) and, since Phase 13, into every audit event
  the request produces — both `src/policies/gateway.py` and `src/evidence/persist.py` now read
  the live trace ID (`src/monitoring/tracing.current_trace_id()`) instead of always writing
  `correlation_id=None` — verified live end-to-end, `src/monitoring/README.md` § Incident
  reconstruction.
- **Idempotency:** `POST /cases/{case_id}/review` (approve and reject both) requires an
  idempotency key so a retried request cannot double-execute (`docs/architecture.md` § 11) —
  **IMPLEMENTED**, Phase 9's `action_executions` mechanism, reused here
  (`src/policies/gateway.py`'s `approve_pending_action`).
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
