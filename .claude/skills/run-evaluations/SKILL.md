---
description: Workflow for running this project's evaluation suite (tests, golden cases, model/LLM evaluation, security tests) and reporting results honestly. Use when asked to evaluate, benchmark, or report on system quality/safety, or before claiming a roadmap phase's exit criteria are met.
---

# Run Evaluations

Run whichever of the following actually exist in the repository right now — check
`docs/project-status.md` first; do not assume a command exists because `docs/evaluation-plan.md`
describes it as the target state.

1. Unit tests
2. Integration tests
3. Golden cases (`evaluation/golden_cases/`)
4. Regression tests
5. Adversarial/red-team tests (`docs/guardrails.md` § 4)
6. Policy tests (tool-authorization chain, allow and deny paths)
7. Privacy/security tests
8. Model evaluation (`docs/model-evaluation.md`)
9. LLM evaluation (`docs/model-evaluation.md` § 8)

For each, record: the exact command run, the result (pass/fail counts, or the actual metric
value), any failures with their cause, known limitations (sample size, what wasn't covered),
the environment it ran in, and the relevant model/prompt/policy/dataset versions
(`docs/model-evaluation.md` § 7).

Apply the labeling rule from `docs/evaluation-plan.md` § 1 to every number reported:
`MEASURED` (from this actual run), `SIMULATED`/`OFFLINE`, or `PROJECTED`. Never present a
`PROJECTED` or `SIMULATED` number as `MEASURED`.

**Never fabricate results.** If a metric can't be computed (missing dependency, no trained
model yet, no dataset loaded), report `not available` and why — do not estimate a plausible-
looking number instead. If `python -m evaluation.run` (`docs/evaluation-plan.md` § 9) doesn't
exist yet, say so and run whatever partial evaluation does exist instead of pretending the
full suite ran.

When reporting against `docs/evaluation-plan.md` §§ 2–8 categories or the baseline comparison
in § 10, state the sample size and denominator for every rate (e.g., "0 unsafe outcomes out of
12 adversarial cases" — not "0 unsafe outcomes"). Zero observed failures in a small test set
does not establish zero risk — say so explicitly per `docs/evaluation-plan.md` § 8.
