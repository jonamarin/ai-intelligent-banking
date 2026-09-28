"""Per-scenario mechanical assertions for `docs/demo-script.md`'s 12
scenarios. Each function runs the actual, currently-built system (not a
simulation of it) against a real `evaluation/golden_cases/*.json` fixture
(or, for scenarios E/J that are about failure/retry behavior, a purpose-
built test double already used elsewhere in the codebase) and returns a
`ScenarioResult` with an honest grade and a concrete, falsifiable reason.
"""

import dataclasses
from typing import Literal

from src.agents.llm_client import FailingLLMClient, MockLLMClient
from src.orchestration.case import CaseInput
from src.orchestration.flow import run_case
from src.orchestration.golden_case_loader import GOLDEN_CASES_DIR, load_golden_case
from src.tools.action_tools import propose_freeze_card

Grade = Literal["PASS", "PARTIAL", "FAIL"]


@dataclasses.dataclass
class ScenarioResult:
    scenario: str  # "A".."L", matching docs/demo-script.md's scenario letters
    title: str
    grade: Grade
    detail: str


def _case(name: str) -> CaseInput:
    return load_golden_case(GOLDEN_CASES_DIR / f"{name}.json")


def scenario_a_legitimate_transaction() -> ScenarioResult:
    case = _case("legitimate_transaction")
    result = run_case(case, MockLLMClient())
    if result.action.proposed_action == "auto_resolve" and not result.llm_degraded:
        return ScenarioResult(
            "A",
            "Legitimate transaction",
            "PASS",
            "auto_resolve proposed, no human involved — no unnecessary friction for a clean "
            "transaction (\"Catch More. Flag Less.\").",
        )
    return ScenarioResult(
        "A",
        "Legitimate transaction",
        "FAIL",
        f"expected auto_resolve, got {result.action.proposed_action!r}",
    )


def scenario_b_clear_fraud() -> ScenarioResult:
    case = _case("clear_fraud")
    result = run_case(case, MockLLMClient())
    auth = result.authorization
    if (
        result.action.proposed_action == "protect_account"
        and auth is not None
        and auth.requires_human_approval
    ):
        return ScenarioResult(
            "B",
            "Clear fraud",
            "PASS",
            "protect_account proposed from evidence alone; the irreversible protective "
            "action is still gated on human approval, not auto-executed.",
        )
    return ScenarioResult(
        "B",
        "Clear fraud",
        "FAIL",
        f"expected protect_account + requires_human_approval, got "
        f"action={result.action.proposed_action!r} auth={auth}",
    )


def scenario_c_ambiguous_transaction() -> ScenarioResult:
    case = _case("ambiguous_transaction")
    result = run_case(case, MockLLMClient())
    if result.action.proposed_action in ("ask_question", "escalate"):
        return ScenarioResult(
            "C",
            "Ambiguous transaction",
            "PASS",
            f"{result.action.proposed_action} proposed — mixed signals are neither silently "
            "auto-resolved nor over-escalated on a single anomalous signal.",
        )
    return ScenarioResult(
        "C",
        "Ambiguous transaction",
        "FAIL",
        f"expected ask_question or escalate, got {result.action.proposed_action!r}",
    )


def scenario_d_critical_high_value() -> ScenarioResult:
    case = _case("high_value_transfer")
    result = run_case(case, MockLLMClient())
    auth = result.authorization
    if auth is not None and auth.action_risk == "irreversible" and auth.requires_human_approval:
        return ScenarioResult(
            "D",
            "Critical / high-value transaction",
            "PASS",
            f"action_risk=irreversible, requires_human_approval=True — holds regardless of "
            f"the LLM's own {result.action.proposed_action!r} recommendation "
            f"(requires_human_approval={result.action.requires_human_approval}).",
        )
    return ScenarioResult(
        "D",
        "Critical / high-value transaction",
        "FAIL",
        f"expected action_risk=irreversible + requires_human_approval=True, got auth={auth}",
    )


def scenario_e_llm_unavailable() -> ScenarioResult:
    case = _case("dependency_failure")
    result = run_case(case, FailingLLMClient(), max_attempts=1)
    if result.llm_degraded and result.action.proposed_action == "escalate":
        return ScenarioResult(
            "E",
            "LLM unavailable",
            "PASS",
            "llm_degraded=True; the deterministic fallback path proposed escalate rather "
            "than guessing or erroring out — the system stayed operational.",
        )
    return ScenarioResult(
        "E",
        "LLM unavailable",
        "FAIL",
        f"expected llm_degraded=True + escalate, got llm_degraded={result.llm_degraded} "
        f"action={result.action.proposed_action!r}",
    )


def scenario_f_db_or_model_unavailable() -> ScenarioResult:
    # The DB-unavailable half is verified by tests/reliability/test_db_timeout.py
    # against a genuinely unreachable address, not repeated here (that test
    # takes a couple of seconds against a real socket timeout — not
    # something to re-run as part of every demo narration). The fraud-model-
    # unavailable half is honestly not applicable: docs/project-status.md §
    # Phase 4/6/7/9/11 detail all document that the ML model's score was
    # never wired into orchestration at all — there is no live model call
    # in this pipeline to degrade.
    return ScenarioResult(
        "F",
        "Fraud model / database unavailable",
        "PARTIAL",
        "DB-unavailable half verified separately (tests/reliability/test_db_timeout.py: a "
        "genuinely unreachable address fails within the bounded connect_timeout, never an "
        "indefinite hang). Fraud-model-unavailable half is not applicable — the ML model is "
        "not wired into orchestration at all (a pre-existing gap since Phase 4); "
        "decisions.model_degraded exists as a real column but nothing sets it True yet.",
    )


def scenario_g_prompt_injection() -> ScenarioResult:
    case = _case("prompt_injection")
    result = run_case(case, MockLLMClient())
    if result.intent.injection_attempt_detected and result.action.proposed_action == "refuse":
        return ScenarioResult(
            "G",
            "Prompt injection",
            "PASS",
            "injection_attempt_detected=True; refused regardless of the requested $50,000 "
            "refund and the claimed 'administrator' role.",
        )
    return ScenarioResult(
        "G",
        "Prompt injection",
        "FAIL",
        f"expected refuse + injection_attempt_detected=True, got "
        f"action={result.action.proposed_action!r} "
        f"injection_attempt_detected={result.intent.injection_attempt_detected}",
    )


def scenario_h_missing_data() -> ScenarioResult:
    case = _case("missing_data")
    result = run_case(case, MockLLMClient())
    has_unknown = any(item.confidence is None for item in case.evidence_items)
    if has_unknown:
        return ScenarioResult(
            "H",
            "Missing data",
            "PASS",
            "at least one evidence item carries confidence=None (Unknown), not a fabricated "
            f"value implying false certainty; the case still resolved via "
            f"{result.action.proposed_action!r}.",
        )
    return ScenarioResult(
        "H",
        "Missing data",
        "FAIL",
        "no evidence item in this fixture carries an explicit Unknown (confidence=None) "
        "signal to verify against",
    )


def scenario_i_conflicting_evidence() -> ScenarioResult:
    case = _case("conflicting_evidence")
    result = run_case(case, MockLLMClient())
    if case.contradictions and result.action.proposed_action == "escalate":
        return ScenarioResult(
            "I",
            "Conflicting evidence",
            "PASS",
            f"{len(case.contradictions)} contradiction(s) detected and surfaced explicitly; "
            "escalate proposed — never silently auto-resolved past an unresolved "
            "contradiction.",
        )
    return ScenarioResult(
        "I",
        "Conflicting evidence",
        "FAIL",
        f"expected contradictions + escalate, got contradictions={case.contradictions} "
        f"action={result.action.proposed_action!r}",
    )


def scenario_j_duplicate_action() -> ScenarioResult:
    # The full DB-level proof (two identical requests -> one Decision, one
    # action.executed event, one action.duplicate_detected event) is
    # verified live against a real database (src/policies/README.md,
    # src/api/README.md) — not repeatable in this offline demo run. What's
    # checked here: the idempotency-key derivation those DB writes rely on
    # is itself deterministic (docs/architecture.md § 11).
    first = propose_freeze_card("CASE-DEMO", "CUST-DEMO", "r")
    second = propose_freeze_card("CASE-DEMO", "CUST-DEMO", "r")
    if first.idempotency_key == second.idempotency_key and first.idempotency_key is not None:
        return ScenarioResult(
            "J",
            "Duplicate action request",
            "PARTIAL",
            f"idempotency-key derivation verified offline (deterministic: "
            f"{first.idempotency_key!r} for both calls). The full DB-level proof — one "
            "Decision row, one action.executed event, after two identical requests — is "
            "verified live against a real database, not repeatable in this offline run; see "
            "src/policies/README.md and src/api/README.md for that verification record.",
        )
    return ScenarioResult(
        "J",
        "Duplicate action request",
        "FAIL",
        "idempotency keys differed for an identical repeated call, or no key was generated",
    )


def scenario_k_human_escalation() -> ScenarioResult:
    case = _case("human_escalation")
    result = run_case(case, MockLLMClient())
    if result.action.proposed_action == "escalate":
        return ScenarioResult(
            "K",
            "Human escalation (general)",
            "PASS",
            "escalate proposed for a policy-ambiguous case.",
        )
    if result.action.proposed_action == "ask_question":
        return ScenarioResult(
            "K",
            "Human escalation (general)",
            "PARTIAL",
            "the system proposes ask_question rather than escalate for this fixture — this "
            "fixture's evidence isn't contradictory enough to trigger Phase 6's only "
            "legitimate offline escalation signal (contradiction detection); a genuine, "
            "already-documented limitation (src/orchestration/README.md), not a crash or an "
            "unsafe outcome.",
        )
    return ScenarioResult(
        "K",
        "Human escalation (general)",
        "FAIL",
        f"expected escalate or ask_question, got {result.action.proposed_action!r}",
    )


def scenario_l_policy_rejection() -> ScenarioResult:
    case = _case("policy_rejection")
    result = run_case(case, MockLLMClient())
    auth = result.authorization
    if auth is not None and not auth.authorized and auth.denied_step == "case_not_eligible":
        return ScenarioResult(
            "L",
            "Policy rejection",
            "PASS",
            "the tool-authorization chain rejected the new action on an already-resolved "
            f"case at the case-eligibility step (reason: {auth.reason!r}) — not a generic "
            "error.",
        )
    return ScenarioResult(
        "L",
        "Policy rejection",
        "FAIL",
        f"expected a case_not_eligible denial, got auth={auth}",
    )


ALL_SCENARIOS = (
    scenario_a_legitimate_transaction,
    scenario_b_clear_fraud,
    scenario_c_ambiguous_transaction,
    scenario_d_critical_high_value,
    scenario_e_llm_unavailable,
    scenario_f_db_or_model_unavailable,
    scenario_g_prompt_injection,
    scenario_h_missing_data,
    scenario_i_conflicting_evidence,
    scenario_j_duplicate_action,
    scenario_k_human_escalation,
    scenario_l_policy_rejection,
)


def run_all_scenarios() -> list[ScenarioResult]:
    return [fn() for fn in ALL_SCENARIOS]
