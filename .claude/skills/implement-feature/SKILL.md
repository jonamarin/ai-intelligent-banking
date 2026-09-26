---
description: Workflow for implementing a feature or roadmap phase in this repository — inspect first, plan, implement a vertical slice, test, verify security/observability, update docs. Use whenever asked to build, add, or implement functionality (not for pure research/explanation tasks).
---

# Implement Feature

Follow this sequence. Do not skip to step 7.

1. **Understand the requirement.** What is actually being asked? Which `docs/
   implementation-roadmap.md` phase(s) does it belong to? If it doesn't map cleanly to a
   phase, check whether it should — out-of-sequence work (e.g., UI before the policy engine
   exists) is a red flag, not a shortcut.
2. **Inspect the current implementation.** Read `docs/project-status.md` first — do not assume
   anything is built because a `docs/` file describes it. Read the actual relevant code, if
   any exists.
3. **Inspect architecture/domain documentation.** At minimum: `docs/architecture.md` (where
   this fits), `docs/domain-model.md` (what entities are involved), and the specific owning
   doc for this subject (`CLAUDE.md` § 11 has the ownership table). If the feature touches
   decision logic, also read `docs/decision-policy.md` and `docs/guardrails.md`.
4. **Identify affected boundaries.** Which layer(s) does this touch — API, orchestration,
   tools, policy, data, UI? Check `.claude/rules/` for that layer's specific rules.
5. **Create an implementation plan** for anything non-trivial, architectural, security-
   sensitive, or cross-cutting (`CLAUDE.md` § 6). Use plan mode; don't silently start writing
   code for a large change.
6. **Define acceptance criteria** before writing code — what does "done" look like, concretely
   (which test passes, which scenario in `docs/demo-script.md` now works)?
7. **Implement a vertical slice** — something runnable end-to-end for its scope, not a
   disconnected layer (`docs/implementation-roadmap.md` intro).
8. **Add tests** per `.claude/rules/testing.md` — happy path, invalid input, unauthorized
   access, and any relevant failure/adversarial case.
9. **Validate security/privacy** — does this touch PII, authentication, authorization, a
   financial action, or a tool? If so, apply `.claude/rules/security.md` and consider running
   the `review-security` skill before calling it done.
10. **Validate observability** — does this add a new decision, action, or state change that
    needs an audit event (`docs/observability.md` § 3)? Add it now, not as follow-up.
11. **Update documentation** — `docs/project-status.md` at minimum; the owning `docs/` file if
    the implementation revealed a gap or a needed correction to the design (and consider
    whether it needs an ADR per `docs/decisions/README.md`).
12. **Run verification** — use the `verify-implementation` skill to find and run the actual
    discovered lint/typecheck/test commands. Never claim tests pass without having run them.
13. **Review the diff** before considering the change complete — does it match what steps 5–6
    intended, with no unrelated changes mixed in?
14. **Report remaining risks** — what's untested, what's a known limitation, what would need
    to happen before this could be considered production-ready (`docs/implementation-
    roadmap.md`'s "risks" field for the relevant phase is a good reference).

Never implement blindly against a requirement you haven't traced back to its owning `docs/`
file. Never skip straight to writing code for anything non-trivial.
