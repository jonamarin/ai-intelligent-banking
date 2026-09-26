# Frontend Rules

Applies to the UI built in Phase 10 (`docs/implementation-roadmap.md`). Framework is not yet
chosen (`docs/architecture.md` § 15, `OPEN QUESTION`) — these rules apply regardless of the
eventual framework.

- All API access goes through a typed client generated or hand-matched against
  `docs/api-contracts.md`; never construct ad-hoc fetch calls with inline URLs scattered
  through components.
- Every screen that reflects a security- or authorization-sensitive state (case status, action
  availability) re-derives that state from the API response, not from client-side assumptions
  — the UI is not the authorization boundary (`docs/architecture.md` § 14).
- **Never visually imply certainty the backend evidence doesn't support**
  (`docs/domain-model.md` § 4, `prompt.md` § 36). If a field is a model prediction, label it as
  one; if evidence is `Unknown`/`insufficient`, show that state, not a blank or a guess.
- The customer view never exposes internal risk scores, model internals, or raw evidence
  identifiers (`prompt.md` § 35 — "Do not expose internal risk details"). The analyst view is
  the only place that detail belongs.
- The evidence-graph view (`prompt.md` § 36) must visually distinguish **supports fraud**,
  **supports legitimate**, **unknown**, and **contradiction** as four genuinely different
  states — not shades of the same color implying a spectrum where none is claimed.
- Human-review/approval controls are only rendered for an authenticated analyst/supervisor
  session — never conditionally hidden-but-reachable for a customer session.
- Handle loading, error, and empty states explicitly for every data-dependent view; a
  dependency failure (`docs/architecture.md` § 10) should surface as a clear, safe UI state,
  not a blank screen or a stack trace.
- Accessibility: usable with keyboard navigation and screen readers at minimum for the
  customer-facing chat view — this is a banking product, not a demo toy.
- Before reporting frontend work as complete, start the dev server and exercise the golden
  path and at least one edge case in a real browser — type-checking is not feature
  verification.
