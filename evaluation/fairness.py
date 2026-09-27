"""Fairness evaluation (`docs/evaluation-plan.md` § 7,
`docs/model-evaluation.md` § 13): compare the Hybrid pipeline's outcome
rates across `country` (and `segment`, where the subgroup is large enough
to say anything) — never used as a decision input, only as an evaluation
slice, exactly as both documents require.

Every subgroup result carries its own sample size, and a subgroup below
`MIN_SUBGROUP_SIZE` is reported as `"insufficient sample size"` rather than
a point estimate that would be pure noise at this scale
(`docs/model-evaluation.md` § 13: "Sample-size limitations must be stated
per subgroup ... report that honestly rather than suppressing the
subgroup").
"""

from typing import Any, TypedDict

MIN_SUBGROUP_SIZE = 5


class SubgroupOutcome(TypedDict):
    sample_size: int
    fraud_count: int
    automation_rate: float | None  # share of cases auto_resolve'd (no human involved)
    escalation_rate: float | None  # share of cases flagged (protect_account/escalate/etc.)
    false_positive_rate: float | None  # among is_fraud=False: share flagged
    false_negative_rate: float | None  # among is_fraud=True: share NOT flagged
    note: str


def _rate(numerator: int, denominator: int) -> float | None:
    return (numerator / denominator) if denominator else None


def _subgroup_outcome(records: list[dict[str, Any]]) -> SubgroupOutcome:
    n = len(records)
    if n < MIN_SUBGROUP_SIZE:
        return SubgroupOutcome(
            sample_size=n,
            fraud_count=sum(1 for r in records if r["is_fraud"]),
            automation_rate=None,
            escalation_rate=None,
            false_positive_rate=None,
            false_negative_rate=None,
            note=f"insufficient sample size (n={n} < {MIN_SUBGROUP_SIZE}) — not reported",
        )

    automated = sum(1 for r in records if r["proposed_action"] == "auto_resolve")
    flagged = sum(1 for r in records if r["flagged"])
    legit = [r for r in records if not r["is_fraud"]]
    fraud = [r for r in records if r["is_fraud"]]
    fp = sum(1 for r in legit if r["flagged"])
    fn = sum(1 for r in fraud if not r["flagged"])

    return SubgroupOutcome(
        sample_size=n,
        fraud_count=len(fraud),
        automation_rate=_rate(automated, n),
        escalation_rate=_rate(flagged, n),
        false_positive_rate=_rate(fp, len(legit)),
        false_negative_rate=_rate(fn, len(fraud)),
        note=f"MEASURED, n={n} (small-sample point estimate — see docs/model-evaluation.md § 13)",
    )


def fairness_by_attribute(
    records: list[dict[str, Any]], attribute: str
) -> dict[str, SubgroupOutcome]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = str(record.get(attribute) or "unknown")
        groups.setdefault(key, []).append(record)
    return {key: _subgroup_outcome(recs) for key, recs in sorted(groups.items())}
