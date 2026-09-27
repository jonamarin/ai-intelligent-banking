"""Case orchestrator: the explicit state machine driving a case through the
pipeline in docs/architecture.md § 2. See flow.py for the Phase 6 (mock LLM
mode) implementation — everything it produces is a proposal, never an
executed action (docs/guardrails.md § 1)."""
