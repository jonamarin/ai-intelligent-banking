"""Narrated CLI walkthrough of all 12 `docs/demo-script.md` scenarios.

    uv run python -m demo.run

Fully offline — no DB, no API key (matching every scenario's own
underlying fixture/test-double). Exits non-zero if any scenario is graded
`FAIL`, so this doubles as a CI-friendly smoke check
(`docs/implementation-roadmap.md` Phase 12: "make demo reproduces every
scenario's documented expected outcome") — `PARTIAL` does not fail the
run: it means a real, already-documented, non-unsafe limitation, not a
broken guarantee. See `demo/scenarios.py` for exactly what's asserted per
scenario, and `demo/README.md` for the full, honestly-graded result.
"""

import sys

from demo.scenarios import ScenarioResult, run_all_scenarios

_GRADE_MARK = {"PASS": "+", "PARTIAL": "~", "FAIL": "X"}


def _print_result(result: ScenarioResult) -> None:
    mark = _GRADE_MARK[result.grade]
    print(f"\n[{mark}] Scenario {result.scenario} — {result.title}: {result.grade}")
    print(f"    {result.detail}")


def main() -> int:
    results = run_all_scenarios()
    for result in results:
        _print_result(result)

    counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0}
    for result in results:
        counts[result.grade] += 1

    print(
        f"\n{len(results)} scenarios: {counts['PASS']} PASS, {counts['PARTIAL']} PARTIAL, "
        f"{counts['FAIL']} FAIL"
    )
    if counts["FAIL"]:
        print("\nFAIL means a documented guarantee did not hold — see the scenario detail above.")
        return 1
    if counts["PARTIAL"]:
        print(
            "\nPARTIAL means a real, already-documented, non-unsafe limitation — not a "
            "broken guarantee. See demo/README.md for what each one means and why."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
