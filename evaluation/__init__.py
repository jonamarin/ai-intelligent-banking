"""System-level evaluation (Phase 11, docs/evaluation-plan.md).

    uv run python -m evaluation.run

`golden_cases/` holds the hand-authored adversarial/scenario fixtures used
since Phase 6; the modules in this package (`sample.py`, `baselines.py`,
`fairness.py`, `report.py`, `run.py`) implement the system-level evaluation
run itself — model, business, LLM/agent, fairness, and baseline-comparison
metrics, every number labeled MEASURED/SIMULATED/PROJECTED/"not available"
per `docs/evaluation-plan.md` § 1.
"""
