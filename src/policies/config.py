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

    # Whether policy allows automatic (no human) execution at each action-risk
    # level. High defaults to False (a human must approve every High-risk
    # action, e.g. freeze_card, until a policy owner says otherwise) — a
    # conservative default per .claude/rules/security.md's "secure defaults"
    # rule, not a business decision this repository is authorized to loosen.
    automate_low_risk: bool = True
    automate_medium_risk: bool = True
    automate_high_risk: bool = False
