"""Action-risk classification (docs/decision-policy.md § 6) — a fixed lookup
table in code. **The LLM cannot talk its way into a lower action-risk
classification for a given action type** (docs/decision-policy.md § 6): the
classification here never reads `customer_message`, an LLM's stated
confidence, or an `ActionProposal.reason` string — only the tool being
proposed and the case's own structured facts (transaction type, amount).

An unrecognized `tool_name` classifies as `"high"`, never `"low"` — a secure
default (`.claude/rules/security.md`: "a new endpoint, tool, or feature
starts locked down"). A monetary action is escalated to `"irreversible"` the
moment its USD-equivalent amount meets the configured threshold, or its
transaction/requested-action type is inherently irreversible (transfer,
account closure, beneficiary change) — independent of, and never overridden
by, whatever action-risk a `ToolProposal` itself carries. The trained fraud
model's score (`src/ml/score.py`, read via `fraud_model_score` below) is a
third, independent override of the same shape, finally wiring
`docs/decision-policy.md` § 5's risk bands to a real score.
"""

from typing import Literal

from src.policies.config import PolicyConfig

ActionRisk = Literal["low", "medium", "high", "irreversible"]

_RISK_ORDER: dict[ActionRisk, int] = {"low": 0, "medium": 1, "high": 2, "irreversible": 3}

# docs/decision-policy.md § 6's table, keyed by tool_name (src/tools/*.py).
TOOL_ACTION_RISK: dict[str, ActionRisk] = {
    "get_customer": "low",
    "get_transaction": "low",
    "get_recent_transactions": "low",
    "get_merchant_profile": "low",
    "create_human_review": "low",
    "close_case_no_action": "low",
    "notify_customer": "medium",
    "create_dispute": "medium",
    "freeze_card": "high",
}

# Transaction/requested-action types that are Irreversible/Critical
# unconditionally, regardless of amount (docs/decision-policy.md § 6 row 4:
# "Account closure, large transfer, beneficiary change, major financial
# adjustment"). Matched case-insensitively, spaces normalized to underscores.
_ALWAYS_IRREVERSIBLE_TYPES = {
    "transfer",
    "large_transfer",
    "account_closure",
    "beneficiary_change",
}


def max_risk(a: ActionRisk, b: ActionRisk) -> ActionRisk:
    return a if _RISK_ORDER[a] >= _RISK_ORDER[b] else b


def _requested_action_override(
    *,
    transaction_type: str | None,
    requested_action: str | None,
    amount_usd: float | None,
    requested_amount_usd: float | None,
    threshold: float,
) -> ActionRisk | None:
    for value in (transaction_type, requested_action):
        if value and value.strip().lower().replace(" ", "_") in _ALWAYS_IRREVERSIBLE_TYPES:
            return "irreversible"
    for amount in (amount_usd, requested_amount_usd):
        if amount is not None and amount >= threshold:
            return "irreversible"
    return None


def _fraud_score_override(
    fraud_model_score: float | None, *, high_threshold: float, critical_threshold: float
) -> ActionRisk | None:
    """docs/decision-policy.md § 5's risk bands, finally wired to a real
    score (src/ml/score.py) — can only ever escalate action-risk, same as
    `_requested_action_override` above; `None` (no live score available,
    src/orchestration/case.py's own docstring on why) changes nothing."""
    if fraud_model_score is None:
        return None
    if fraud_model_score >= critical_threshold:
        return "irreversible"
    if fraud_model_score >= high_threshold:
        return "high"
    return None


def classify_action_risk(
    tool_name: str,
    *,
    transaction_type: str | None = None,
    requested_action: str | None = None,
    amount_usd: float | None = None,
    requested_amount_usd: float | None = None,
    fraud_model_score: float | None = None,
    config: PolicyConfig | None = None,
) -> ActionRisk:
    config = config or PolicyConfig()
    result = TOOL_ACTION_RISK.get(tool_name, "high")
    amount_override = _requested_action_override(
        transaction_type=transaction_type,
        requested_action=requested_action,
        amount_usd=amount_usd,
        requested_amount_usd=requested_amount_usd,
        threshold=config.large_amount_threshold_usd,
    )
    if amount_override:
        result = max_risk(result, amount_override)
    score_override = _fraud_score_override(
        fraud_model_score,
        high_threshold=config.high_fraud_score_threshold,
        critical_threshold=config.critical_fraud_score_threshold,
    )
    if score_override:
        result = max_risk(result, score_override)
    return result
