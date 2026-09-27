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
"""

import datetime as dt
import uuid
from typing import Any, Literal, cast

from sqlalchemy import Table, select
from sqlalchemy.engine import Engine

from src.models import AuditEvent, Decision, Evidence, FraudCase, HumanReview, decision_evidence
from src.orchestration.case import CaseInput, CaseResult
from src.security.redaction import redact_value

ReviewAction = Literal["approve", "reject", "modify", "request_more_evidence"]


def persist_decision(engine: Engine, case: CaseInput, result: CaseResult, model_name: str) -> str:
    """Writes one Decision (+ linked evidence, + audit events) for a case
    that has already run through `flow.run_case`. Returns the new
    `decision_id`. No-op-safe to call once per case turn — call again for a
    later turn, don't call it twice for the same result."""
    decision_id = str(uuid.uuid4())
    now = dt.datetime.now(dt.UTC)
    auth = result.authorization

    decisions_table = cast(Table, Decision.__table__)
    evidence_table = cast(Table, Evidence.__table__)
    audit_events_table = cast(Table, AuditEvent.__table__)
    fraud_cases_table = cast(Table, FraudCase.__table__)

    with engine.begin() as conn:
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
                explanation=result.explanation.analyst_explanation,
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
        payload = redact_value(_decision_payload(case, result))
        conn.execute(
            audit_events_table.insert(),
            [
                {
                    "audit_event_id": str(uuid.uuid4()),
                    "event_type": event_type,
                    "case_id": case.case_id,
                    "decision_id": decision_id,
                    "correlation_id": None,
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

    return decision_id


def approve_pending_action(
    engine: Engine,
    *,
    case_id: str,
    decision_id: str,
    reviewer_id: str,
    action: ReviewAction,
    rationale: str | None = None,
) -> str:
    """A human's action on a case gated by `persist_decision` — never merged
    into the `Decision` record (`docs/human-oversight.md` § 4). Returns the
    new `review_id`."""
    review_id = str(uuid.uuid4())
    now = dt.datetime.now(dt.UTC)

    human_reviews_table = cast(Table, HumanReview.__table__)
    audit_events_table = cast(Table, AuditEvent.__table__)
    fraud_cases_table = cast(Table, FraudCase.__table__)

    with engine.begin() as conn:
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
                correlation_id=None,
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

    return review_id


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
