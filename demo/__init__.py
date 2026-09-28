"""Scripted, deterministic walkthroughs of `docs/demo-script.md`'s 12
scenarios (Phase 12).

    uv run python -m demo.run

Every scenario gets one honest grade — `PASS`, `PARTIAL`, or `FAIL` — never
a forced binary pass when the evidence doesn't support one
(`docs/domain-model.md` § 4's own rule, applied here to grading the demo
itself, not just to fraud decisions). `scenarios.py` holds the mechanical
assertion for each; deliberately **not** a prose-matching grader against
each golden case's own free-text `expected_*` fields
(`src/orchestration/run_golden_cases.py`'s own documented reason for not
doing that — fragile, falsely-precise pseudo-validation). Each check is a
specific, hand-written assertion about what the actually-built system does.
"""
