"""Evidence Engine CLI (docs/implementation-roadmap.md Phase 5).

    DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
      uv run python -m src.evidence.build_case --refresh-devices --transaction-id <ID>

    # or let it pick a real fraud=True transaction from the loaded sample:
    DATABASE_URL="..." uv run python -m src.evidence.build_case --refresh-devices --pick-fraud

`--refresh-devices` (re)derives the `devices` table from currently-loaded
`digital_events` — run it at least once before building any evidence graph,
and again whenever more digital_events have been ingested.
"""

import argparse

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.evidence.device import refresh_devices
from src.evidence.graph import build_evidence_graph
from src.evidence.persist import persist_evidence_graph, save_graph_json
from src.models.base import get_engine


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


def _refresh_devices(engine: Engine) -> None:
    with engine.connect() as conn:
        events = pd.read_sql(
            "SELECT event_id, event_date, customer_id, ip_address, platform, browser "
            "FROM digital_events",
            conn,
        )
    n = refresh_devices(engine, events)
    print(f"Refreshed devices table: {n} device rows upserted from {len(events)} events.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction-id", type=str, default=None)
    parser.add_argument(
        "--pick-fraud",
        action="store_true",
        help="Pick the most recent is_fraud=true transaction instead of specifying one.",
    )
    parser.add_argument(
        "--refresh-devices",
        action="store_true",
        help="Re-derive the devices table from currently-loaded digital_events first.",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Optional path to save graph JSON."
    )
    parser.add_argument(
        "--no-persist", action="store_true", help="Build and print only; don't write to the DB."
    )
    args = parser.parse_args()

    if not args.transaction_id and not args.pick_fraud:
        raise SystemExit("Specify --transaction-id or --pick-fraud.")

    engine = get_engine()

    if args.refresh_devices:
        _refresh_devices(engine)

    transaction_id = args.transaction_id or _pick_fraud_transaction_id(engine)
    graph = build_evidence_graph(engine, transaction_id)

    print(f"\nEvidence graph for transaction {transaction_id} (case {graph.case_id}):")
    for item in graph.items:
        conf = f"{item.confidence:.2f}" if item.confidence is not None else "Unknown"
        print(f"  [{item.direction.value:<20}] conf={conf:<7} {item.type}: {item.value}")
    print(f"  Contradictions: {len(graph.contradictions)}")
    for a, b in graph.contradictions:
        print(f"    {a} <-> {b}")

    if not args.no_persist:
        persist_evidence_graph(engine, graph)
        print(f"\nPersisted: fraud_cases row {graph.case_id}, {len(graph.items)} evidence rows.")

    if args.output:
        save_graph_json(graph, args.output)
        print(f"Graph JSON saved to {args.output}")


if __name__ == "__main__":
    main()
