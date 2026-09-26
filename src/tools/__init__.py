"""Typed tool implementations (get_customer, create_dispute, freeze_card, ...).

Every tool is schema-validated, authenticated, authorized, audited, timed-out,
and retried per docs/architecture.md § 6. The LLM never gets raw database access
— only these tools. Filled in starting Phase 6/7 (docs/implementation-roadmap.md).
"""
