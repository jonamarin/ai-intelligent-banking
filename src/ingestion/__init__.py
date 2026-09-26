"""LATAM Bank dataset ingestion (docs/implementation-roadmap.md Phase 3).

Loads the CSV files in data/raw/ (docs/data-lineage.md § 1) into the schema
created in Phase 2 (src/models/). Only the tables this workflow actually
uses are loaded — see docs/data-dictionary.md § Tables not used for what's
deliberately skipped (branches, service_agents, marketing_campaigns,
campaign_sends, satisfaction_surveys).

Entry point: `python -m src.ingestion.run` (see run.py for CLI flags).
"""
