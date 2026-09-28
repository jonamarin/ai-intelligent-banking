"""Persists an EvidenceGraph (graph.py) as real rows: one FraudCase, N
Evidence rows (append-only — no update/delete path exists at the tool layer,
docs/guardrails.md § 4), and an AuditEvent (docs/observability.md § 3).

Does NOT compute or store a risk_score or a Decision — that needs the Phase
4 model and the Phase 7 policy engine wired together, which is orchestration
(Phase 6) work, not this phase's job. `FraudCase.risk_score` and `.decision`
are left null here, honestly, rather than half-integrated.

`AuditEvent.payload` is passed through `redact_value` (Phase 8,
src/security/redaction.py) before it's written — a structural guarantee,
not just convention (docs/security-model.md § 7: "redaction happens before
the write, not as a downstream filter").
"""

import datetime as dt
import json
import uuid
from typing import Any, cast

from sqlalchemy import Table
from sqlalchemy.engine import Engine

from src.evidence.graph import EvidenceGraph
from src.models import AuditEvent, Evidence, FraudCase
from src.monitoring import tracing
from src.security.redaction import redact_value


def persist_evidence_graph(engine: Engine, graph: EvidenceGraph) -> None:
    fraud_cases_table = cast(Table, FraudCase.__table__)
    evidence_table = cast(Table, Evidence.__table__)
    audit_events_table = cast(Table, AuditEvent.__table__)

    with engine.begin() as conn:
        conn.execute(
            fraud_cases_table.insert().values(
                case_id=graph.case_id,
                customer_id=graph.customer_id,
                transaction_id=graph.transaction_id,
                created_at=graph.created_at,
                status="under_review",
                escalation_required=bool(graph.contradictions),
            )
        )
        if graph.items:
            conn.execute(
                evidence_table.insert(),
                [
                    {
                        "evidence_id": item.evidence_id,
                        "case_id": graph.case_id,
                        "source": item.source,
                        "type": item.type,
                        "value": item.value,
                        "direction": item.direction,
                        "confidence": item.confidence,
                        "timestamp": item.timestamp,
                        "provenance": item.provenance,
                    }
                    for item in graph.items
                ],
            )
        conn.execute(
            audit_events_table.insert().values(
                audit_event_id=str(uuid.uuid4()),
                event_type="evidence.graph.created",
                case_id=graph.case_id,
                decision_id=None,
                correlation_id=tracing.current_trace_id(),
                payload=redact_value(_audit_payload(graph)),
                created_at=dt.datetime.now(dt.UTC),
            )
        )


def _audit_payload(graph: EvidenceGraph) -> dict[str, Any]:
    return {
        "transaction_id": graph.transaction_id,
        "customer_id": graph.customer_id,
        "evidence_count": len(graph.items),
        "contradiction_count": len(graph.contradictions),
        "evidence_types": [item.type for item in graph.items],
    }


def save_graph_json(graph: EvidenceGraph, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, indent=2, default=str)
