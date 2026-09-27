"""The deterministic fallback path for Scenario E (`docs/demo-script.md`:
"LLM unavailable") — used only when the configured `LLMClient` raises,
whether from a provider timeout/error or from returning structured output
that fails schema validation (`docs/architecture.md` § 10's "Malformed
model/tool output" row: "reject and retry with backoff up to a bound, then
escalate").

This is deliberately **not** a second, fancier LLM client — it's the
"traditional fraud model still runs -> policy engine still runs -> human
escalation" path from `docs/architecture.md` § 10, minus the LLM-assisted
parts (explanation generation, next-best-question selection) that
genuinely can't happen without it. Intent detection stays available (it's
local keyword matching, not a provider call), but the fallback always routes
to `escalate` rather than trusting a partial/degraded recommendation for an
account-affecting action — degrading gracefully, never guessing.
"""

import re

from src.agents.llm_client import INJECTION_PATTERNS
from src.agents.schemas import ActionProposal, CaseExplanation, IntentResult, NextQuestionDecision

FALLBACK_MODEL_NAME = "fallback-deterministic-v0.1.0"


def fallback_extract_intent(message: str) -> IntentResult:
    """Local keyword/regex matching only — no provider call, so this stays
    available even when the configured LLMClient itself is unreachable."""
    lower = message.lower()
    injection = any(re.search(p, lower) for p in INJECTION_PATTERNS)
    if injection:
        return IntentResult(
            intent="unsupported_or_unsafe_request",
            confidence=0.9,
            injection_attempt_detected=True,
        )
    # Without a working LLM, intent beyond "is this an injection attempt" is
    # not reliably inferable — report low confidence honestly rather than
    # guess a specific intent (docs/domain-model.md § 4: never force false
    # certainty).
    return IntentResult(intent="general_inquiry", confidence=0.0)


def fallback_next_question() -> NextQuestionDecision:
    """Never ask a question in degraded mode — expected-information-gain
    scoring is LLM-assisted (docs/architecture.md § 8); guessing whether a
    question is worth the customer friction without it is worse than not
    asking. Escalating is the safe default instead."""
    return NextQuestionDecision(
        should_ask=False,
        rationale="LLM unavailable — next-best-question scoring requires it; escalating "
        "instead of guessing whether a clarifying question is worth asking.",
    )


def fallback_propose_action(injection_attempt_detected: bool) -> ActionProposal:
    if injection_attempt_detected:
        return ActionProposal(
            proposed_action="refuse",
            reason="Customer message attempted to override system instructions or claimed "
            "unearned authority — refused regardless of content, independent of LLM "
            "availability (docs/security-model.md § 2).",
            requires_human_approval=False,
        )
    return ActionProposal(
        proposed_action="escalate",
        reason="LLM unavailable — routing to a human rather than resolving automatically "
        "without the LLM's narrative/evidence-weighing step (docs/demo-script.md Scenario E).",
        requires_human_approval=True,
    )


def fallback_explain(action: ActionProposal) -> CaseExplanation:
    return CaseExplanation(
        customer_explanation_es="Tu caso requiere revisión adicional. Un especialista lo "
        "atenderá en breve.",
        analyst_explanation=(
            f"[LLM_DEGRADED] proposed_action={action.proposed_action}; reason={action.reason}; "
            f"model={FALLBACK_MODEL_NAME}. Full evidence/explanation generation was "
            "unavailable — this case was NOT reasoned about by the LLM; treat the analyst "
            "explanation above as a placeholder, not evidence-grounded reasoning."
        ),
    )
