"""Structured LLM outputs (docs/model-evaluation.md § 8; docs/guardrails.md § 2).

Every LLM-facing function in this package returns one of these — never raw
text parsed ad hoc downstream. `IntentResult`/`NextQuestionDecision`/
`ActionProposal` are PROPOSALS: nothing here authorizes an action
(docs/decision-policy.md § 2). Confidence fields are always in [0, 1] and
`extra="forbid"` so an LLM (real or mock) can't smuggle unexpected fields
through — a malformed/out-of-schema response is a validation error, not a
best-effort guess (docs/guardrails.md § 2, "structured-output schema").
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal[
    "unrecognized_transaction",
    "refund_request",
    "card_lost_stolen",
    "general_inquiry",
    "unsupported_or_unsafe_request",
]


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    entities: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    # True when the customer message tried to instruct the system directly
    # (docs/security-model.md § 2) — never derived from *acting* on the
    # instruction, only from detecting the attempt, so this flag itself is
    # safe to set from untrusted input.
    injection_attempt_detected: bool = False


class NextQuestionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_ask: bool
    question_es: str | None = None
    expected_information_gain: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str


class ActionProposal(BaseModel):
    """A PROPOSAL only — docs/decision-policy.md § 2: AI recommendation !=
    authorization. Phase 7's policy engine (not implemented) is the only
    thing allowed to turn this into an executed action."""

    model_config = ConfigDict(extra="forbid")

    proposed_action: Literal[
        "auto_resolve", "ask_question", "create_dispute", "protect_account", "escalate", "refuse"
    ]
    reason: str
    requires_human_approval: bool


class CaseExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_explanation_es: str  # plain language, no internal risk details (prompt.md § 22)
    analyst_explanation: str  # technical, cites evidence + versions (prompt.md § 22)
