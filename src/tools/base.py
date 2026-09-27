"""Tool result/proposal shapes (docs/architecture.md § 6; prompt.md § 16, § 17).

Every tool in this package is one of two kinds:
- **Read tools** (`read_tools.py`): actually query the database. Low action-risk
  (prompt.md § 15 — "retrieve information ... can be automated"), so they
  execute directly.
- **Action tools** (`action_tools.py`): construct and return a `ToolProposal`
  — they never write to the database. The authorization chain
  (`src/policies/authorization.py`, Phase 7) decides whether a proposal may
  execute; the actual DB write for a live case happens in
  `src/policies/gateway.py`, which is idempotency-key-aware (Phase 9,
  `idempotency_key` below) — a proposal alone is still always safe to
  construct, nothing here writes anything.
"""

import dataclasses
from typing import Any


@dataclasses.dataclass
class ToolProposal:
    tool_name: str
    arguments: dict[str, Any]
    rationale: str
    action_risk: str  # "low" | "medium" | "high" | "irreversible" — docs/decision-policy.md § 6
    requires_human_approval: bool
    # docs/architecture.md § 11: "actions with financial or state-changing
    # effects ... require an idempotency key derived from the case and
    # action type so a retried or duplicated request cannot execute twice."
    # `action_tools.py`'s propose_* functions default this to
    # f"{case_id}-{tool_name}" when not given explicitly.
    idempotency_key: str | None = None
