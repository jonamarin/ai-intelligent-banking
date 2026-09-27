"""Provider-agnostic LLM client (docs/architecture.md § 15, § 5; prompt.md § 8).

Only `MockLLMClient` is implemented and verified in this phase — a real
provider integration (Claude / OpenAI-compatible) is deliberately **not**
built here: this environment has no authorized API key, and fabricating an
untested provider class would violate CLAUDE.md § 7's "never fabricate
capabilities." `get_llm_client` raises `NotImplementedError` for
`LLM_MODE=live` rather than pretending it works. `LLM_MODE=mock` is a hard
requirement anyway (prompt.md § 52) — every test, CI run, and the golden-case
suite in this phase runs against `MockLLMClient` only.

`MockLLMClient` is deliberately **deterministic, rule-based** logic, not
randomness — the same input always produces the same output (required for
reproducibility, docs/model-evaluation.md § 11), and it's honestly documented
as a simulation of plausible LLM behavior for offline development/testing,
never presented as a real model's output.
"""

import re
from typing import Protocol

from src.agents.schemas import ActionProposal, CaseExplanation, IntentResult, NextQuestionDecision
from src.config.settings import Settings

MODEL_NAME_MOCK = "mock-rule-based-v0.1.0"

# Phrasings that attempt to override system instructions via customer text
# (docs/security-model.md § 2, docs/guardrails.md § 4). Detecting these is
# safe from untrusted input; *acting* on them is never done anywhere in this
# codebase — see docs/guardrails.md § 3 (the authorization chain doesn't
# consult conversation content at all). Public (not `_`-prefixed): reused by
# src/orchestration/fallback.py's Scenario E deterministic fallback path
# (Phase 9), which must detect injection attempts without depending on a
# working LLM provider — same patterns, single source of truth, not a copy.
INJECTION_PATTERNS = [
    r"ignora\s+tus?\s+instruccion",
    r"ignore\s+(your\s+)?(previous\s+)?instructions",
    r"soy\s+el\s+administrador",
    r"i\s+am\s+the\s+(bank\s+)?administrator",
    r"desactiva\s+(las?\s+)?(validac|verificac)",
    r"disable\s+(the\s+)?(fraud\s+)?check",
    # Additional instruction-override/authority-claim shapes found by
    # tests/security/test_red_team.py (Phase 8) — the two attack shapes are
    # always the same (claim of authority; instruction override), phrased
    # more ways than the original six patterns caught.
    r"olvida\s+(todo\s+)?lo\s+anterior",
    r"forget\s+(everything\s+)?(you\s+were\s+told|above|previous)",
    r"developer\s+mode",
    r"modo\s+desarrollador",
    r"ignore\s+all\s+(safety\s+)?rules",
    r"soy\s+el\s+(dueñ|propietari)o\s+del\s+sistema",
    r"i\s+(am|'m)\s+the\s+(owner|creator)\s+of\s+(the\s+)?system",
]

_INTENT_KEYWORDS: list[tuple[str, str]] = [
    (r"no reconozco|don'?t recognize|unrecognized", "unrecognized_transaction"),
    (r"reembolso|refund", "refund_request"),
    (r"tarjeta.*(perdid|robad)|card.*(lost|stolen)", "card_lost_stolen"),
]


class LLMClient(Protocol):
    def extract_intent(self, message: str) -> IntentResult: ...

    def decide_next_question(
        self, uncertainty_summary: str, candidate_questions: list[str]
    ) -> NextQuestionDecision: ...

    def propose_action(
        self, evidence_summary: str, contradiction_count: int, escalation_required: bool
    ) -> ActionProposal: ...

    def explain(self, evidence_summary: str, proposal: ActionProposal) -> CaseExplanation: ...


class MockLLMClient:
    """Deterministic, rule-based simulation — never a real model. See module
    docstring."""

    model_name = MODEL_NAME_MOCK

    def extract_intent(self, message: str) -> IntentResult:
        lower = message.lower()
        injection = any(re.search(p, lower) for p in INJECTION_PATTERNS)

        intent = "general_inquiry"
        entities: dict[str, str] = {}
        for pattern, matched_intent in _INTENT_KEYWORDS:
            if re.search(pattern, lower):
                intent = matched_intent
                break

        amount_match = re.search(r"\$?\s?([\d,]+(?:\.\d+)?)", message)
        if amount_match:
            entities["amount"] = amount_match.group(1).replace(",", "")

        if injection:
            # Detecting the attempt is fine; the customer's demand is never
            # treated as an instruction — see docs/guardrails.md § 4.
            return IntentResult(
                intent="unsupported_or_unsafe_request",
                entities=entities,
                confidence=0.9,
                injection_attempt_detected=True,
            )

        return IntentResult(
            intent=intent,  # type: ignore[arg-type]
            entities=entities,
            confidence=0.8 if intent != "general_inquiry" else 0.4,
        )

    def decide_next_question(
        self, uncertainty_summary: str, candidate_questions: list[str]
    ) -> NextQuestionDecision:
        if not candidate_questions:
            return NextQuestionDecision(
                should_ask=False,
                rationale="No candidate questions available.",
            )
        # Deterministic heuristic (docs/architecture.md § 8): ask only when
        # the uncertainty summary signals a real conflict, not on every
        # ambiguous-but-uncontested case — avoids unnecessary friction
        # (prompt.md § 20).
        gain = 0.6 if "contradiction" in uncertainty_summary.lower() else 0.2
        should_ask = gain >= 0.5
        return NextQuestionDecision(
            should_ask=should_ask,
            question_es=candidate_questions[0] if should_ask else None,
            expected_information_gain=gain,
            rationale=(
                "Contradictory evidence detected — one targeted question is likely to "
                "resolve it." if should_ask else "Evidence is not conflicting enough to "
                "justify customer friction from an additional question."
            ),
        )

    def propose_action(
        self, evidence_summary: str, contradiction_count: int, escalation_required: bool
    ) -> ActionProposal:
        lower = evidence_summary.lower()
        if escalation_required or contradiction_count > 0:
            return ActionProposal(
                proposed_action="escalate",
                reason=f"{contradiction_count} contradiction(s) in the evidence graph — "
                "routing to a human rather than guessing.",
                requires_human_approval=True,
            )
        if "supports_fraud" in lower:
            return ActionProposal(
                proposed_action="protect_account",
                reason="Evidence supporting fraud found, no contradictions.",
                requires_human_approval=True,
            )
        return ActionProposal(
            proposed_action="auto_resolve",
            reason="Evidence is consistent and supports legitimacy or is neutral.",
            requires_human_approval=False,
        )

    def explain(self, evidence_summary: str, proposal: ActionProposal) -> CaseExplanation:
        customer_text = {
            "auto_resolve": "Revisamos la transacción y no encontramos señales de actividad "
            "sospechosa. No se requiere ninguna acción adicional de tu parte.",
            "ask_question": "Necesitamos confirmar un detalle contigo antes de continuar.",
            "create_dispute": "Hemos iniciado una disputa para esta transacción mientras "
            "la investigamos.",
            "protect_account": "Detectamos actividad inusual y estamos protegiendo tu cuenta "
            "mientras la revisamos.",
            "escalate": "Tu caso requiere revisión de un especialista antes de continuar. "
            "Te contactaremos pronto.",
            "refuse": "No podemos procesar esta solicitud tal como fue planteada.",
        }[proposal.proposed_action]
        analyst_text = (
            f"proposed_action={proposal.proposed_action}; reason={proposal.reason}; "
            f"model={self.model_name}; evidence_summary={evidence_summary}"
        )
        return CaseExplanation(
            customer_explanation_es=customer_text, analyst_explanation=analyst_text
        )


class FailingLLMClient:
    """Test double simulating an unavailable/timing-out LLM provider (Phase
    9, `docs/demo-script.md` Scenario E) — every method raises `TimeoutError`
    unconditionally. Used by `tests/reliability/` to prove
    `src/orchestration/flow.py`'s retry-then-fallback path actually
    activates, not just that it's documented. Never used outside tests."""

    model_name = "failing-test-double"

    def extract_intent(self, message: str) -> IntentResult:
        raise TimeoutError("simulated LLM provider timeout")

    def decide_next_question(
        self, uncertainty_summary: str, candidate_questions: list[str]
    ) -> NextQuestionDecision:
        raise TimeoutError("simulated LLM provider timeout")

    def propose_action(
        self, evidence_summary: str, contradiction_count: int, escalation_required: bool
    ) -> ActionProposal:
        raise TimeoutError("simulated LLM provider timeout")

    def explain(self, evidence_summary: str, proposal: ActionProposal) -> CaseExplanation:
        raise TimeoutError("simulated LLM provider timeout")


class FlakyLLMClient:
    """Test double that fails its first `fail_first_n` calls (any method)
    with `TimeoutError`, then delegates to a real `MockLLMClient` — proves
    the retry budget in `src/orchestration/retry.py` genuinely retries
    rather than only ever falling back on the first failure. Never used
    outside tests."""

    model_name = MockLLMClient.model_name

    def __init__(self, fail_first_n: int) -> None:
        self._remaining_failures = fail_first_n
        self._delegate = MockLLMClient()

    def _maybe_fail(self) -> None:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise TimeoutError("simulated transient LLM provider failure")

    def extract_intent(self, message: str) -> IntentResult:
        self._maybe_fail()
        return self._delegate.extract_intent(message)

    def decide_next_question(
        self, uncertainty_summary: str, candidate_questions: list[str]
    ) -> NextQuestionDecision:
        self._maybe_fail()
        return self._delegate.decide_next_question(uncertainty_summary, candidate_questions)

    def propose_action(
        self, evidence_summary: str, contradiction_count: int, escalation_required: bool
    ) -> ActionProposal:
        self._maybe_fail()
        return self._delegate.propose_action(
            evidence_summary, contradiction_count, escalation_required
        )

    def explain(self, evidence_summary: str, proposal: ActionProposal) -> CaseExplanation:
        self._maybe_fail()
        return self._delegate.explain(evidence_summary, proposal)


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockLLMClient()
    raise NotImplementedError(
        "LLM_MODE=live has no implemented provider in this project yet — only mock mode "
        "is built and verified (docs/project-status.md § Phase 6 detail). Implementing a "
        "real provider requires an authorized API key this environment does not have."
    )
