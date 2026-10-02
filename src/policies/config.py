"""Policy configuration (docs/decision-policy.md § 10).

Every threshold here is `PROPOSED`, not business-approved — this repository
implements the *mechanism* that reads a configured threshold, it does not
invent the business number (docs/decision-policy.md § 10: "This repository
implements the mechanism; it does not manufacture the business number").
A real deployment must replace these defaults with values a policy owner
actually signs off on.

`automate_irreversible` deliberately does not exist as a field: Irreversible/
Critical actions never auto-execute, full stop (docs/demo-script.md Scenario
D) — that guarantee is hardcoded in `authorization.py`, not something an
environment variable could ever weaken.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class PolicyConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLICY_", extra="ignore")

    policy_version: str = "policy-v0.1.0-proposed"

    # PROPOSED (docs/decision-policy.md § 10) — the USD-equivalent amount at
    # or above which ANY monetary action is classified Irreversible/Critical,
    # regardless of which tool nominally carries it (docs/decision-policy.md § 6).
    large_amount_threshold_usd: float = 10_000.0

    # PROPOSED (docs/decision-policy.md § 5's own illustrative risk bands,
    # now actually wired in — src/policies/action_risk.py). The fraud
    # model's score (src/ml/score.py) escalates action-risk the same way a
    # large amount already does: >= critical forces "irreversible"
    # (mandatory human approval, no automation at any config), >= high
    # forces at least "high". These are the exact band boundaries
    # docs/decision-policy.md § 5 wrote before any model existed to feed
    # them — not re-derived, not business-approved either, same caveat as
    # large_amount_threshold_usd above.
    high_fraud_score_threshold: float = 0.70
    critical_fraud_score_threshold: float = 0.90

    # Whether policy allows automatic (no human) execution at each action-risk
    # level. High defaults to False (a human must approve every High-risk
    # action, e.g. freeze_card, until a policy owner says otherwise) — a
    # conservative default per .claude/rules/security.md's "secure defaults"
    # rule, not a business decision this repository is authorized to loosen.
    automate_low_risk: bool = True
    automate_medium_risk: bool = True
    automate_high_risk: bool = False
