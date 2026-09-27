"""Case endpoints (`docs/api-contracts.md` § 1) — the first live consumer of
Phases 6-9's orchestration/policy engine over HTTP, not just the CLI
scripts (`run_golden_cases.py`, `live_case.py`). Every write here calls the
exact same functions those scripts call (`src.orchestration.live_case.
create_and_run_case`, `src.policies.gateway.approve_pending_action`) — this
router is a thin HTTP adapter, not a second implementation.

Authentication/authorization is the trusted-test-identity abstraction in
`src/api/deps.py` — see that module's docstring; every endpoint here is
correctly scoped against it, but it is not a real identity system.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.api.deps import Role, get_current_role, get_db_engine, require_reviewer_role
from src.api.errors import AppError, NotFoundError
from src.api.schemas import (
    AnalystCaseView,
    AuditEventOut,
    CaseCreateResponse,
    CaseListItem,
    CreateCaseRequest,
    CustomerCaseView,
    DecisionOut,
    EvidenceItemOut,
    ReviewRequest,
    ReviewResponse,
    SessionRequest,
)
from src.evidence.graph import EvidenceDirection, EvidenceItem, detect_contradictions
from src.orchestration.live_case import create_and_run_case
from src.policies.gateway import approve_pending_action

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


def _fetch_case_row(engine: Engine, case_id: str) -> Any:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT case_id, customer_id, transaction_id, status, decision, "
                "decision_reason, escalation_required, human_review_status "
                "FROM fraud_cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id},
        ).fetchone()
    if row is None:
        raise NotFoundError(f"Case {case_id} not found.")
    return row


def _fetch_evidence(engine: Engine, case_id: str) -> list[EvidenceItem]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT evidence_id, source, type, value, direction, confidence, "
                "timestamp, provenance FROM evidence WHERE case_id = :case_id "
                "ORDER BY timestamp"
            ),
            {"case_id": case_id},
        ).fetchall()
    return [
        EvidenceItem(
            evidence_id=row.evidence_id,
            source=row.source,
            type=row.type,
            value=row.value,
            direction=EvidenceDirection(row.direction),
            confidence=float(row.confidence) if row.confidence is not None else None,
            timestamp=row.timestamp,
            provenance=row.provenance,
        )
        for row in rows
    ]


def _fetch_latest_decision(engine: Engine, case_id: str) -> Any:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT decision_id, decision, model_version, policy_version, confidence, "
                "analyst_explanation, customer_explanation_es, llm_degraded, model_degraded, "
                "created_at FROM decisions WHERE case_id = :case_id "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"case_id": case_id},
        ).fetchone()


def _fetch_audit_trail(engine: Engine, case_id: str) -> list[AuditEventOut]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT event_type, created_at FROM audit_events "
                "WHERE case_id = :case_id ORDER BY created_at"
            ),
            {"case_id": case_id},
        ).fetchall()
    return [AuditEventOut(event_type=r.event_type, created_at=r.created_at) for r in rows]


@router.post("", response_model=CaseCreateResponse)
def create_case(
    body: CreateCaseRequest, engine: Engine = Depends(get_db_engine)
) -> CaseCreateResponse:
    outcome = create_and_run_case(engine, body.transaction_id, persist=True)
    auth = outcome.result.authorization
    return CaseCreateResponse(
        case_id=outcome.case.case_id,
        transaction_id=body.transaction_id,
        decision_id=outcome.decision_id,
        was_duplicate=outcome.was_duplicate,
        proposed_action=outcome.result.action.proposed_action,
        requires_human_approval=auth.requires_human_approval if auth else None,
        authorized=auth.authorized if auth else None,
        llm_degraded=outcome.result.llm_degraded,
    )


@router.get("", response_model=list[CaseListItem])
def list_cases(
    limit: int = 20,
    engine: Engine = Depends(get_db_engine),
    _role: Role = Depends(require_reviewer_role),
) -> list[CaseListItem]:
    """The analyst review queue — never reachable for a customer session
    (`.claude/rules/frontend.md`)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT case_id, customer_id, status, decision, human_review_status, "
                "created_at FROM fraud_cases ORDER BY created_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).fetchall()
    return [
        CaseListItem(
            case_id=r.case_id,
            customer_id=r.customer_id,
            status=r.status,
            decision=r.decision,
            human_review_status=r.human_review_status,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{case_id}")
def get_case(
    case_id: str,
    engine: Engine = Depends(get_db_engine),
    role: Role = Depends(get_current_role),
) -> CustomerCaseView | AnalystCaseView:
    case_row = _fetch_case_row(engine, case_id)
    latest_decision = _fetch_latest_decision(engine, case_id)

    if role == "customer":
        return CustomerCaseView(
            case_id=case_row.case_id,
            status=case_row.status,
            customer_explanation_es=(
                latest_decision.customer_explanation_es if latest_decision else None
            ),
        )

    items = _fetch_evidence(engine, case_id)
    contradictions = [list(pair) for pair in detect_contradictions(items)]
    return AnalystCaseView(
        case_id=case_row.case_id,
        customer_id=case_row.customer_id,
        transaction_id=case_row.transaction_id,
        status=case_row.status,
        decision=case_row.decision,
        decision_reason=case_row.decision_reason,
        human_review_status=case_row.human_review_status,
        escalation_required=case_row.escalation_required,
        evidence=[
            EvidenceItemOut(
                evidence_id=item.evidence_id,
                type=item.type,
                value=item.value,
                direction=item.direction.value,
                confidence=item.confidence,
                provenance=item.provenance,
            )
            for item in items
        ],
        contradictions=cast(list[list[str]], contradictions),
        latest_decision=(
            DecisionOut(
                decision_id=latest_decision.decision_id,
                decision=latest_decision.decision,
                model_version=latest_decision.model_version,
                policy_version=latest_decision.policy_version,
                confidence=(
                    float(latest_decision.confidence)
                    if latest_decision.confidence is not None
                    else None
                ),
                analyst_explanation=latest_decision.analyst_explanation,
                customer_explanation_es=latest_decision.customer_explanation_es,
                llm_degraded=latest_decision.llm_degraded,
                model_degraded=latest_decision.model_degraded,
                created_at=latest_decision.created_at,
            )
            if latest_decision
            else None
        ),
        audit_trail=_fetch_audit_trail(engine, case_id),
    )


@router.post("/{case_id}/review", response_model=ReviewResponse)
def review_case(
    case_id: str,
    body: ReviewRequest,
    engine: Engine = Depends(get_db_engine),
    role: Role = Depends(require_reviewer_role),
) -> ReviewResponse:
    case_row = _fetch_case_row(engine, case_id)
    if case_row.human_review_status != "pending":
        raise AppError(
            f"Case {case_id} has no pending review (human_review_status="
            f"{case_row.human_review_status!r}).",
            code="no_pending_review",
            status_code=409,
        )
    latest_decision = _fetch_latest_decision(engine, case_id)
    if latest_decision is None:
        raise AppError(
            f"Case {case_id} has no Decision to review.", code="no_decision", status_code=409
        )

    review_id, was_duplicate = approve_pending_action(
        engine,
        case_id=case_id,
        decision_id=latest_decision.decision_id,
        reviewer_id=body.reviewer_id,
        action=body.action,
        rationale=body.rationale,
    )
    return ReviewResponse(review_id=review_id, was_duplicate=was_duplicate)


@router.post("/session")
def set_session_role(body: SessionRequest, response: Response) -> dict[str, str]:
    """Sets the trusted-test-identity cookie (`src/api/deps.py`) — never a
    real login. An out-of-range role is a 422 (Pydantic validation), not a
    silent fallback to the default."""
    response.set_cookie("role", body.role, httponly=False, samesite="lax")
    return {"role": body.role}
