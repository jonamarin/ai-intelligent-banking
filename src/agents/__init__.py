"""LLM-facing orchestration: intent/entity extraction, RAG, tool proposals.

Everything here produces a proposal, never a direct execution (docs/architecture.md
§ 3, docs/guardrails.md § 1). Filled in starting Phase 6 (docs/implementation-roadmap.md).
"""
