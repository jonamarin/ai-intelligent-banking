# Architecture Decision Records (ADRs)

This directory holds ADRs for decisions that are expensive to reverse, cross-cutting, or
frequently re-litigated if left undocumented. Do not write an ADR for a trivial or easily
reversible choice — put that in the owning `docs/` file directly.

Write an ADR when a decision:

- changes the security, financial-authorization, or human-oversight model,
- picks between architecturally distinct options (e.g., orchestration framework, event
  system, policy-engine design) that would be costly to switch later,
- overrides or narrows something `prompt.md` or a `docs/` file previously specified, or
- resolves a conflict between sources (see § Precedence below) in a way future sessions need
  to know was deliberate.

## Format

```markdown
# ADR-NNNN: <short title>

## Status
Proposed | Accepted | Superseded by ADR-NNNN | Deprecated

## Context
What problem forced this decision? What constraints applied?

## Problem
The specific question being decided.

## Decision
What was decided, stated as a single unambiguous sentence.

## Alternatives considered
Each alternative, with why it was rejected.

## Consequences
What becomes easier or harder as a result. Include negative consequences honestly.

## Security implications
Does this change a trust boundary, authorization path, or data-handling rule? If none, say so.

## Operational implications
Deployment, monitoring, rollback, on-call impact. If none, say so.

## Reversibility
How hard would this be to undo, and what would undoing it cost?

## Open questions
Anything left unresolved by this decision.
```

Number ADRs sequentially (`ADR-0001-...md`, `ADR-0002-...md`) in this directory. No ADRs exist
yet — this repository initialization did not make any decision of ADR-worthy weight; it
proposed a stack and structure, all still labeled `PROPOSED` in `docs/architecture.md`.

## Source-of-truth precedence

Multiple documents describe this system: `prompt.md` (the original master prompt),
`project_presentation.txt` (the competition brief), the `docs/` files, and, eventually, the
implementation itself. When they disagree:

1. `CLAUDE.md` owns persistent Claude Code operating instructions.
2. Each `docs/` file owns its subject per the ownership table in `CLAUDE.md` § 11.
3. An **Accepted** ADR overrides the `docs/` file it amends, for the subject it addresses.
4. `docs/project-status.md` owns what is verified to be implemented — code and tests are
   evidence of actual behavior, but they do not silently override a documented business
   requirement that hasn't been implemented yet (that's a gap, not a decision).
5. `prompt.md` and `project_presentation.txt` are historical design input, not authoritative
   over later decisions recorded in `docs/` or an ADR.

Do not silently pick a side when sources conflict:

1. State the conflict explicitly wherever it surfaces (code comment is not enough — say it to
   the user or record it as `OPEN QUESTION` in the relevant `docs/` file).
2. Prefer the document that owns the subject, if it reflects a later approved decision.
3. Check for a relevant ADR.
4. Check implementation evidence.
5. If still unresolved, mark it `OPEN QUESTION` or `BLOCKED` in `docs/project-status.md` — do
   not guess at a business decision (thresholds, compliance claims, approved policy).
6. Do not modify `prompt.md` unless explicitly asked to — it is the historical record of what
   was originally requested.
