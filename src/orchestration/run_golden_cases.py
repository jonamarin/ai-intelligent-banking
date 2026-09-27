"""Runs every evaluation/golden_cases/*.json through the orchestration flow
in LLM_MODE=mock (docs/implementation-roadmap.md Phase 6 exit criteria:
"LLM_MODE=mock produces deterministic, reproducible output for each
evaluation/golden_cases/ scenario"). Fully offline — no database, no API key.

    uv run python -m src.orchestration.run_golden_cases

A case whose fixture sets `synthetic_input.injected_fault` to mention an LLM
outage (e.g. `evaluation/golden_cases/dependency_failure.json`'s
`"llm_provider_timeout_then_fraud_model_service_unavailable"`) is run
through `FailingLLMClient` (Phase 9, `src/agents/llm_client.py`) instead of
the normal `MockLLMClient` — so Scenario E's fallback path
(`src/orchestration/fallback.py`) is genuinely exercised against that
fixture, not merely documented as an intent.

This does NOT auto-grade each case against its free-text `prohibited_outcome`
— reliably parsing arbitrary prose into a pass/fail check would be fragile,
falsely-precise pseudo-validation. Instead it reports the chosen action
alongside the case's `prohibited_outcome` and `expected_human_involvement`
text so a human (or a future Phase 11 automated grader with a real rubric,
docs/evaluation-plan.md § 12) can compare them. `tests/unit/test_flow.py`
does assert real, mechanically-checkable properties (e.g. "action is never
auto_resolve when escalation_required" — see that file for exactly what's
actually verified, vs. what's merely reported here for review.
"""

import argparse
import json
from pathlib import Path

from src.agents.llm_client import FailingLLMClient, LLMClient, MockLLMClient
from src.orchestration.flow import run_case
from src.orchestration.golden_case_loader import GOLDEN_CASES_DIR, load_all_golden_cases
from src.retrieval.policy_rag import PolicyRAG


def _llm_client_for(golden: dict) -> LLMClient:
    fault = str(golden.get("synthetic_input", {}).get("injected_fault", "")).lower()
    if "llm" in fault:
        return FailingLLMClient()
    return MockLLMClient()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-path", type=Path, default=Path("data/reports/golden_case_run.json")
    )
    args = parser.parse_args()

    rag = PolicyRAG()
    cases = load_all_golden_cases()

    report_cases = []
    for case in cases:
        golden = json.loads((GOLDEN_CASES_DIR / f"{case.case_id}.json").read_text(encoding="utf-8"))
        llm_client = _llm_client_for(golden)
        result = run_case(case, llm_client, rag, max_attempts=1)

        report_cases.append(
            {
                "case_id": case.case_id,
                "result": result.to_dict(),
                "for_review": {
                    "expected_human_involvement": golden.get("expected_human_involvement"),
                    "prohibited_outcome": golden.get("prohibited_outcome"),
                },
            }
        )

        print(f"\n{case.case_id}:")
        if result.llm_degraded:
            print("  [!] llm_degraded=True (Scenario E fallback path exercised)")
        print(f"  intent: {result.intent.intent} (confidence={result.intent.confidence:.2f})")
        if result.intent.injection_attempt_detected:
            print("  [!] injection_attempt_detected=True")
        print(
            f"  action: {result.action.proposed_action} "
            f"(human_approval={result.action.requires_human_approval})"
        )
        print(f"  policy_source: {result.policy_source}")
        print(f"  [for human review] expected_human_involvement: "
              f"{golden.get('expected_human_involvement')}")

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        json.dumps({"cases": report_cases}, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n{len(cases)} golden cases run. Report written to {args.report_path}")


if __name__ == "__main__":
    main()
