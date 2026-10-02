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

`fraud_model_score` (Phase 15, src/ml/score.py) is the trained fraud
model's score for this transaction, consulted here for the first time —
`None`/`model_degraded=True` if the model hasn't been trained yet
(`uv run python -m src.ml.train`) or this transaction isn't in the cached
feature sample.
"""

import argparse
import dataclasses
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.evidence.graph import EvidenceGraph, build_evidence_graph
from src.ml.score import score_transaction
from src.orchestration.case import CaseInput, CaseResult

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
    # Phase 15 (docs/project-status.md § Phase 15 detail): the trained
    # fraud model's score, finally consulted at decision time. `None` means
    # the model artifact isn't available yet (a fresh clone before
    # `uv run python -m src.ml.train`) or this transaction_id isn't in the
    # cached feature sample (src/ml/score.py) -- either way,
    # model_degraded=True, mirroring llm_degraded (Phase 9).
    fraud_model_score = score_transaction(engine, graph.transaction_id)
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
        fraud_model_score=fraud_model_score,
        model_degraded=fraud_model_score is None,
    )


@dataclasses.dataclass
class LiveCaseOutcome:
    case: CaseInput
    result: CaseResult
    decision_id: str | None
    was_duplicate: bool


def create_and_run_case(
    engine: Engine, transaction_id: str, *, persist: bool = True
) -> LiveCaseOutcome:
    """The one code path both the CLI (`main()` below) and the API
    (`src/api/cases.py`, Phase 10) use to turn a transaction into a fully
    reasoned, authorized, (optionally) persisted case — build the evidence
    graph, convert it to a `CaseInput`, run it through orchestration, and
    persist the Decision. A CLI printer and a JSON API response each do
    their own presentation on top of these same underlying objects."""
    from src.agents.llm_client import MockLLMClient
    from src.evidence.persist import persist_evidence_graph
    from src.monitoring import tracing
    from src.orchestration.flow import run_case
    from src.policies.gateway import persist_decision
    from src.retrieval.policy_rag import PolicyRAG

    # docs/observability.md § 5 (incident reconstruction from traces + audit
    # log alone): the API layer seeds a trace ID from the request's own
    # X-Correlation-ID (src/api/main.py); a direct CLI/script call has no
    # request to derive one from, so seed a fresh one here if none is
    # already active in this context -- every case run ends up with a real,
    # non-null trace/correlation ID either way.
    if tracing.current_trace_id() is None:
        tracing.seed_trace_id(str(uuid.uuid4()))

    graph = build_evidence_graph(engine, transaction_id)
    if persist:
        persist_evidence_graph(engine, graph)
    case = case_input_from_graph(engine, graph)
    result = run_case(case, MockLLMClient(), PolicyRAG())

    decision_id: str | None = None
    was_duplicate = False
    if persist:
        decision_id, was_duplicate = persist_decision(
            engine, case, result, MockLLMClient.model_name
        )

    return LiveCaseOutcome(
        case=case, result=result, decision_id=decision_id, was_duplicate=was_duplicate
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
    from src.models.base import get_engine
    from src.policies.gateway import persist_decision

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
    parser.add_argument(
        "--persist-twice",
        action="store_true",
        help="With --persist, call persist_decision a second time to demonstrate idempotency "
        "(docs/demo-script.md Scenario J, src/policies/gateway.py).",
    )
    args = parser.parse_args()
    if not args.transaction_id and not args.pick_fraud:
        raise SystemExit("Specify --transaction-id or --pick-fraud.")

    engine = get_engine()
    transaction_id = args.transaction_id or _pick_fraud_transaction_id(engine)
    outcome = create_and_run_case(engine, transaction_id, persist=args.persist)
    case = outcome.case
    result = outcome.result

    print(f"Live case {case.case_id} (transaction {case.transaction_id}):")
    print(f"  customer_message: {case.customer_message[:120]}")
    print(f"  fraud_model_score: {case.fraud_model_score} (model_degraded={result.model_degraded})")
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
        decision_id, was_duplicate = outcome.decision_id, outcome.was_duplicate
        print(f"  persisted: decision_id={decision_id} was_duplicate={was_duplicate}")
        if args.persist_twice:
            from src.agents.llm_client import MockLLMClient

            decision_id_2, was_duplicate_2 = persist_decision(
                engine, case, result, MockLLMClient.model_name
            )
            print(
                f"  persisted again (same case/action): decision_id={decision_id_2} "
                f"was_duplicate={was_duplicate_2} "
                f"(same as first? {decision_id_2 == decision_id})"
            )


if __name__ == "__main__":
    main()
