# AI Agent Rules

Applies to `src/agents/`, `src/orchestration/`, `src/tools/`, and any LLM-integration code
once Phase 6 (`docs/implementation-roadmap.md`) starts. See `docs/guardrails.md` for the full
enforcement-layer model and `docs/decision-policy.md` for the authorization flow this code
must implement faithfully.

- Every LLM call that drives a decision uses a structured-output schema (Pydantic), validated
  before use. Reject and retry (bounded) on malformed output — never silently coerce or guess
  at intent from unstructured text for anything that affects a decision.
- Every tool call the LLM proposes passes through the full authorization chain
  (`docs/architecture.md` § 6) before executing — never let the orchestrator call a tool's
  underlying implementation directly, bypassing the policy engine, "just this once" or for a
  test shortcut.
- Ground every policy-referencing statement in retrieved RAG content with a traceable source;
  if no reliable source is found, say so or escalate — never let the LLM state a policy from
  its own training data (`prompt.md` § 18).
- Preserve evidence provenance on everything the LLM contributes to the evidence graph — an
  LLM-generated hypothesis is stored as a `Hypothesis`, never silently upgraded to `Fact` or
  `Evidence` (`docs/domain-model.md` § 2).
- Represent uncertainty explicitly in every structured output the LLM produces where
  uncertainty is possible — a forced binary output where the schema doesn't allow "unknown" is
  a bug in the schema, not acceptable LLM behavior.
- Customer content and RAG-retrieved content are untrusted; never concatenate them into a
  position in the prompt that a naive implementation would treat as an instruction
  (`docs/security-model.md` § 1–2). Keep instructions and data structurally separated in the
  prompt construction code.
- Minimize context sent to the LLM: retrieve only what the current reasoning step needs, don't
  dump entire retrieved documents when a targeted chunk suffices (`prompt.md` § 40).
- Bound tool-call loops: a hard cap on tool calls per case-turn, with a "loop detected"
  escalation path rather than an infinite/near-infinite retry.
- Track and bound token/cost usage per case (`docs/observability.md` § 6); use the smallest
  model that reliably does the job for classification-style steps, reserving a larger model
  for genuinely complex reasoning (`prompt.md` § 40).
- Bound latency per stage per the targets in `docs/architecture.md` § 12; never trade away a
  safety check to hit a latency target — document the trade-off instead if it can't be met.
- Version every prompt (`prompt_version`) and every policy version referenced by a decision
  (`docs/model-evaluation.md` § 7) — a prompt change without a version bump breaks
  reproducibility.
- Never route the LLM to an unrestricted database connection or an unrestricted financial
  operation:
  ```
  LLM → unrestricted database          # never
  LLM → unrestricted financial operation  # never
  LLM → validated tool request → authorization layer → deterministic policy → authorized action  # required pattern
  ```
- The system must run correctly in `LLM_MODE=mock` with no external API key — this is a hard
  requirement for tests, CI, and demos, not an optional convenience mode
  (`prompt.md` § 8, § 52).
