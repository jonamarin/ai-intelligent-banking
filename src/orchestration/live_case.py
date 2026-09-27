"""Converts a live, DB-backed `EvidenceGraph` (Phase 5, src/evidence/graph.py)
into the same `CaseInput` shape golden cases use (case.py), so run_case()
(flow.py) has exactly one code path for both offline fixtures and real data.

    DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
      uv run python -m src.orchestration.live_case --pick-fraud

`customer_message` is sourced from the customer's own most recent
`call_transcripts.customer_text` row (a real raw-dataset field, never
fabricated) — falling back to `full_text`, then to a clearly-labeled
placeholder when the customer has no transcript at all, which is common in
this sample and is reported as such, not hidden.

`escalation_required` is derived the same way golden_case_loader.py derives
it: `bool(graph.contradictions)` only.

`transaction_type`/`amount_usd`/`case_status` are read from the real
`transactions`/`fraud_cases` rows so the Policy Engine (Phase 7,
src/policies/action_risk.py) classifies action-risk from real transaction
facts, not from anything the LLM said — pass `--persist` to also write a
real Decision/AuditEvent (and, for High/Irreversible actions,
human_review_status='pending') via src/policies/gateway.py.
"""

import argparse

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.evidence.graph import EvidenceGraph, build_evidence_graph
from src.orchestration.case import CaseInput

_PLACEHOLDER_MESSAGE = (
    "[No customer_interactions or call_transcripts message on file for this customer in the "
    "currently loaded sample — synthetic placeholder standing in for a real customer message.] "
    "No reconozco esta transacción."
)


def _latest_customer_message(engine: Engine, customer_id: str) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT COALESCE(customer_text, full_text) AS message FROM call_transcripts "
                "WHERE customer_id = :customer_id ORDER BY process_date DESC LIMIT 1"
            ),
            {"customer_id": customer_id},
        ).fetchone()
    if row is None or not row.message:
        return _PLACEHOLDER_MESSAGE
    return str(row.message)


def _transaction_facts(engine: Engine, transaction_id: str) -> tuple[str | None, float | None]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT transaction_type, amount, currency, amount_usd FROM transactions "
                "WHERE transaction_id = :transaction_id"
            ),
            {"transaction_id": transaction_id},
        ).fetchone()
    if row is None:
        return None, None
    amount_usd = row.amount_usd
    if amount_usd is None and row.currency == "USD":
        amount_usd = row.amount
    return row.transaction_type, float(amount_usd) if amount_usd is not None else None


def _case_status(engine: Engine, case_id: str) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status FROM fraud_cases WHERE case_id = :case_id"),
            {"case_id": case_id},
        ).fetchone()
    return str(row.status) if row is not None else "open"


def build_live_case(engine: Engine, transaction_id: str) -> CaseInput:
    graph = build_evidence_graph(engine, transaction_id)
    return case_input_from_graph(engine, graph)


def case_input_from_graph(engine: Engine, graph: EvidenceGraph) -> CaseInput:
    transaction_type, amount_usd = _transaction_facts(engine, graph.transaction_id)
    return CaseInput(
        case_id=graph.case_id,
        customer_id=graph.customer_id,
        transaction_id=graph.transaction_id,
        customer_message=_latest_customer_message(engine, graph.customer_id),
        evidence_items=graph.items,
        contradictions=graph.contradictions,
        escalation_required=bool(graph.contradictions),
        candidate_questions=[],
        case_status=_case_status(engine, graph.case_id),
        transaction_type=transaction_type,
        amount_usd=amount_usd,
    )


def _pick_fraud_transaction_id(engine: Engine) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT transaction_id FROM transactions WHERE is_fraud = true "
                "ORDER BY transaction_date DESC LIMIT 1"
            )
        ).fetchone()
        if row is None:
            raise SystemExit("No is_fraud=true transaction found in the currently loaded sample.")
        return str(row.transaction_id)


def main() -> None:
    from src.agents.llm_client import MockLLMClient
    from src.evidence.persist import persist_evidence_graph
    from src.models.base import get_engine
    from src.orchestration.flow import run_case
    from src.policies.gateway import persist_decision
    from src.retrieval.policy_rag import PolicyRAG

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction-id", type=str, default=None)
    parser.add_argument(
        "--pick-fraud",
        action="store_true",
        help="Pick the most recent is_fraud=true transaction instead of specifying one.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist the evidence graph and a real Decision/AuditEvent row "
        "(docs/domain-model.md).",
    )
    args = parser.parse_args()
    if not args.transaction_id and not args.pick_fraud:
        raise SystemExit("Specify --transaction-id or --pick-fraud.")

    engine = get_engine()
    transaction_id = args.transaction_id or _pick_fraud_transaction_id(engine)
    graph = build_evidence_graph(engine, transaction_id)
    if args.persist:
        persist_evidence_graph(engine, graph)
    case = case_input_from_graph(engine, graph)
    result = run_case(case, MockLLMClient(), PolicyRAG())

    print(f"Live case {case.case_id} (transaction {case.transaction_id}):")
    print(f"  customer_message: {case.customer_message[:120]}")
    print(f"  intent: {result.intent.intent} (confidence={result.intent.confidence:.2f})")
    print(
        f"  action: {result.action.proposed_action} "
        f"(LLM-recommended human_approval={result.action.requires_human_approval})"
    )
    auth = result.authorization
    if auth is not None:
        print(
            f"  authorization: authorized={auth.authorized} "
            f"requires_human_approval={auth.requires_human_approval} "
            f"action_risk={auth.action_risk} denied_step={auth.denied_step}"
        )
        print(f"  reason: {auth.reason}")
    else:
        print("  authorization: n/a (no tool call proposed for this action)")
    print(f"  policy_source: {result.policy_source}")
    print(f"  contradictions: {len(case.contradictions)}")

    if args.persist:
        decision_id = persist_decision(engine, case, result, MockLLMClient.model_name)
        print(f"  persisted: decision_id={decision_id}")


if __name__ == "__main__":
    main()
