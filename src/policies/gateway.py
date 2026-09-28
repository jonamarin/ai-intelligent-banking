"""The Action Gateway's persistence for a live, DB-backed case: turns an
`AuthorizationResult` (`authorization.py`) into real `Decision` and
`AuditEvent` rows (`docs/domain-model.md` § Decision, § Audit Event), and —
once a human actually acts on a pending one — a `HumanReview` row, kept
structurally distinct from `Decision` on purpose
(`docs/human-oversight.md` § 4).

Golden cases (`golden_case_loader.py`) never call this module — they have no
backing `fraud_cases` row to attach a `Decision` to, and stay fully offline
by design (`docs/project-status.md` § Phase 6 detail). Only `live_case.py`
uses this.

**What this does not do:** actually call an external banking system to
freeze a card or send a transfer — no such system exists in this project
(synthetic dataset only, `CLAUDE.md` § 1). "`action.executed`" here means
exactly one thing: the Decision this repository is authoritative over was
recorded as authorized-and-approved. Wiring a real downstream action gateway
is out of this project's scope.

**Idempotency (Phase 9, docs/architecture.md § 11, docs/demo-script.md
Scenario J):** `persist_decision` is keyed by `AuthorizationResult.
idempotency_key` (defaults to `f"{case_id}-{tool_name}"`,
`src/tools/action_tools.py`). A retried/duplicated call with the same key
is detected via the `action_executions` table's PRIMARY KEY — an
`INSERT ... ON CONFLICT DO NOTHING` race, not a check-then-insert, so this
holds under concurrent duplicate submissions, not just sequential ones
(`.claude/rules/database.md`: "structurally hard, not just policy-forbidden").
A detected duplicate writes exactly one `action.duplicate_detected` audit
event against the *original* `decision_id` and creates no new Decision row.
"""

import datetime as dt
import uuid
from typing import Any, Literal, cast

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from src.models import (
    ActionExecution,
    AuditEvent,
    Decision,
    Evidence,
    FraudCase,
    HumanReview,
    decision_evidence,
)
from src.monitoring import tracing
from src.orchestration.case import CaseInput, CaseResult
from src.security.redaction import redact_value

ReviewAction = Literal["approve", "reject", "modify", "request_more_evidence"]


def persist_decision(
    engine: Engine, case: CaseInput, result: CaseResult, model_name: str
) -> tuple[str, bool]:
    """Writes one Decision (+ linked evidence, + audit events) for a case
    that has already run through `flow.run_case`. Returns
    `(decision_id, was_duplicate)`. Safe to call more than once with an
    equivalent `result` for the same logical action — a duplicate is
    detected via `AuthorizationResult.idempotency_key` and returns the
    *original* `decision_id` with `was_duplicate=True` instead of writing a
    second Decision (docs/demo-script.md Scenario J)."""
    decision_id = str(uuid.uuid4())
    now = dt.datetime.now(dt.UTC)
    auth = result.authorization

    decisions_table = cast(Table, Decision.__table__)
    evidence_table = cast(Table, Evidence.__table__)
    audit_events_table = cast(Table, AuditEvent.__table__)
    fraud_cases_table = cast(Table, FraudCase.__table__)
    action_executions_table = cast(Table, ActionExecution.__table__)

    with engine.begin() as conn:
        if auth is not None and auth.idempotency_key is not None:
            won_race = conn.execute(
                pg_insert(action_executions_table)
                .values(
                    idempotency_key=auth.idempotency_key,
                    case_id=case.case_id,
                    tool_name=auth.tool_name,
                    decision_id=decision_id,
                    result={"proposed_action": result.action.proposed_action},
                    created_at=now,
                )
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(action_executions_table.c.idempotency_key)
            ).fetchone()

            if won_race is None:
                # Someone else already holds this idempotency key — this is
                # a duplicate. Find the original decision, log it, touch
                # nothing else (docs/demo-script.md Scenario J: "return the
                # original result rather than executing a second freeze").
                original = conn.execute(
                    select(action_executions_table.c.decision_id).where(
                        action_executions_table.c.idempotency_key == auth.idempotency_key
                    )
                ).fetchone()
                original_decision_id = original.decision_id if original else decision_id
                conn.execute(
                    audit_events_table.insert().values(
                        audit_event_id=str(uuid.uuid4()),
                        event_type="action.duplicate_detected",
                        case_id=case.case_id,
                        decision_id=original_decision_id,
                        correlation_id=tracing.current_trace_id(),
                        payload=redact_value({"idempotency_key": auth.idempotency_key}),
                        created_at=now,
                    )
                )
                return original_decision_id, True

        conn.execute(
            decisions_table.insert().values(
                decision_id=decision_id,
                case_id=case.case_id,
                decision=result.action.proposed_action,
                model_version=model_name,
                policy_version=auth.policy_version if auth else "n/a",
                # No versioned prompt template exists yet — MockLLMClient is
                # rule-based, not templated.
                prompt_version=None,
                confidence=result.intent.confidence,
                analyst_explanation=result.explanation.analyst_explanation,
                customer_explanation_es=result.explanation.customer_explanation_es,
                llm_degraded=result.llm_degraded,
                created_at=now,
            )
        )

        existing_evidence_ids = {
            row.evidence_id
            for row in conn.execute(
                select(evidence_table.c.evidence_id).where(
                    evidence_table.c.case_id == case.case_id
                )
            )
        }
        linked_ids = [
            item.evidence_id
            for item in case.evidence_items
            if item.evidence_id in existing_evidence_ids
        ]
        if linked_ids:
            conn.execute(
                decision_evidence.insert(),
                [{"decision_id": decision_id, "evidence_id": eid} for eid in linked_ids],
            )

        event_types = auth.audit_event_types if auth else _no_tool_audit_events(result)
        if result.llm_degraded:
            event_types = [*event_types, "llm.degraded"]
        payload = redact_value(_decision_payload(case, result))
        conn.execute(
            audit_events_table.insert(),
            [
                {
                    "audit_event_id": str(uuid.uuid4()),
                    "event_type": event_type,
                    "case_id": case.case_id,
                    "decision_id": decision_id,
                    "correlation_id": tracing.current_trace_id(),
                    "payload": payload,
                    "created_at": now,
                }
                for event_type in event_types
            ],
        )

        pending_human_review = bool(auth and auth.requires_human_approval)
        conn.execute(
            fraud_cases_table.update()
            .where(fraud_cases_table.c.case_id == case.case_id)
            .values(
                decision=result.action.proposed_action,
                decision_reason=result.action.reason,
                human_review_status="pending" if pending_human_review else "not_required",
                status="pending_human_review" if pending_human_review else "resolved",
            )
        )

    return decision_id, False


def approve_pending_action(
    engine: Engine,
    *,
    case_id: str,
    decision_id: str,
    reviewer_id: str,
    action: ReviewAction,
    rationale: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[str, bool]:
    """A human's action on a case gated by `persist_decision` — never merged
    into the `Decision` record (`docs/human-oversight.md` § 4). Returns
    `(review_id, was_duplicate)` — a human's approval click is itself a
    state-changing request and can be retried/double-submitted just like
    any other (`docs/api-contracts.md` § 2: "POST /cases/{case_id}/approve
    and /reject ... require an idempotency key"), reusing the same
    `action_executions` reservation mechanism `persist_decision` uses.
    Default key: `f"{decision_id}-review"` — one human decision per
    Decision, which is the actual business invariant (a second reviewer
    reversing the first is a *new*, explicit action with its own call, not
    a retry of this one)."""
    key = idempotency_key or f"{decision_id}-review"
    review_id = str(uuid.uuid4())
    now = dt.datetime.now(dt.UTC)

    human_reviews_table = cast(Table, HumanReview.__table__)
    audit_events_table = cast(Table, AuditEvent.__table__)
    fraud_cases_table = cast(Table, FraudCase.__table__)
    action_executions_table = cast(Table, ActionExecution.__table__)

    with engine.begin() as conn:
        won_race = conn.execute(
            pg_insert(action_executions_table)
            .values(
                idempotency_key=key,
                case_id=case_id,
                tool_name="human_review",
                decision_id=decision_id,
                result={"action": action},
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(action_executions_table.c.idempotency_key)
        ).fetchone()

        if won_race is None:
            existing = conn.execute(
                select(human_reviews_table.c.review_id).where(
                    human_reviews_table.c.decision_id == decision_id
                )
            ).fetchone()
            original_review_id = existing.review_id if existing else review_id
            conn.execute(
                audit_events_table.insert().values(
                    audit_event_id=str(uuid.uuid4()),
                    event_type="action.duplicate_detected",
                    case_id=case_id,
                    decision_id=decision_id,
                    correlation_id=tracing.current_trace_id(),
                    payload=redact_value({"idempotency_key": key}),
                    created_at=now,
                )
            )
            return original_review_id, True

        conn.execute(
            human_reviews_table.insert().values(
                review_id=review_id,
                case_id=case_id,
                decision_id=decision_id,
                reviewer_id=reviewer_id,
                action=action,
                rationale=rationale,
                created_at=now,
            )
        )
        conn.execute(
            audit_events_table.insert().values(
                audit_event_id=str(uuid.uuid4()),
                event_type="action.executed" if action == "approve" else "action.rejected",
                case_id=case_id,
                decision_id=decision_id,
                correlation_id=tracing.current_trace_id(),
                payload=redact_value(
                    {"reviewer_id": reviewer_id, "action": action, "rationale": rationale}
                ),
                created_at=now,
            )
        )
        conn.execute(
            fraud_cases_table.update()
            .where(fraud_cases_table.c.case_id == case_id)
            .values(
                human_review_status=action,
                status="resolved" if action in ("approve", "reject") else "under_review",
            )
        )

    return review_id, False


def _no_tool_audit_events(result: CaseResult) -> list[str]:
    """Event types for the two outcomes with no `ToolProposal` at all
    (`_tool_proposal_for_action` in flow.py) — `result.authorization` is
    `None`, so this can't come from `AuthorizationResult.audit_event_types`.
    Found during this phase's own security review (`.claude/skills/
    review-security/SKILL.md` § Auditability): an earlier version of this
    function collapsed both outcomes to a single generic
    `risk.assessment.completed` event, silently dropping the
    injection/refusal signal from the audit trail for a live-persisted case."""
    if result.action.proposed_action == "refuse":
        events = ["risk.assessment.completed"]
        if result.intent.injection_attempt_detected:
            events.append("security.injection_attempt_detected")
        events.append("action.rejected")
        return events
    return ["risk.assessment.completed"]  # "ask_question" — no state change to audit beyond this


def _decision_payload(case: CaseInput, result: CaseResult) -> dict[str, Any]:
    auth = result.authorization
    return {
        "customer_id": case.customer_id,
        "transaction_id": case.transaction_id,
        "proposed_action": result.action.proposed_action,
        "action_risk": auth.action_risk if auth else None,
        "requires_human_approval": auth.requires_human_approval if auth else None,
        "authorized": auth.authorized if auth else None,
        "denied_step": auth.denied_step if auth else None,
        "injection_attempt_detected": result.intent.injection_attempt_detected,
        "contradiction_count": len(case.contradictions),
    }
