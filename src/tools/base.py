"""Tool result/proposal shapes (docs/architecture.md § 6; prompt.md § 16, § 17).

Every tool in this package is one of two kinds:
- **Read tools** (`read_tools.py`): actually query the database. Low action-risk
  (prompt.md § 15 — "retrieve information ... can be automated"), so they
  execute directly.
- **Action tools** (`action_tools.py`): construct and return a `ToolProposal`
  — they never write to the database. The authorization chain in
  docs/architecture.md § 6 (authenticated? eligible? sufficient evidence?
  policy allows automation? human approval required?) has no implementation
  yet (Phase 7 — Policy Engine) — until it exists, no action tool may
  execute, full stop. This is enforced by these functions simply not
  containing any write code, not by a runtime check that could be bypassed.
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
