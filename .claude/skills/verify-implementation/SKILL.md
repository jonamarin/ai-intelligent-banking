---
description: Discover and run this repository's actual verification commands (format, lint, typecheck, tests, security checks) before reporting any change complete. Use at the end of any implementation task, and never invent commands that aren't actually in the repo.
---

# Verify Implementation

1. **Discover what actually exists.** Check for `Makefile`, `pyproject.toml`,
   `package.json`, pre-commit config, and CI workflow files. Use only commands you find there
   or that `docs/project-status.md`/`CLAUDE.md` § 9 records as real. If none exist yet (true
   for this repository as of initialization — see `docs/project-status.md`), say so; do not
   invent a `make test` that doesn't exist.
2. Run, where they exist:
   - Formatting check
   - Linting (Ruff, once configured)
   - Type checking (mypy, once configured)
   - Unit tests
   - Integration tests
   - Security checks (`review-security` skill, or an automated security test suite once one
     exists)
   - Evaluation checks (`run-evaluations` skill), if the change touches decision logic or
     model behavior
3. Check documentation is consistent with the change: does `docs/project-status.md` need
   updating? Does the change contradict something in the `docs/` file that owns this subject
   (`CLAUDE.md` § 11)? If so, resolve or flag the conflict per `docs/decisions/README.md`
   rather than leaving it silently inconsistent.
4. Check acceptance criteria defined in the `implement-feature` skill's step 6 were actually
   met.
5. Review `git diff` — does it contain only the intended change? Any accidental inclusion of
   secrets, unrelated files, or debug code?
6. Check for uncommitted changes that shouldn't be left uncommitted, and anything that looks
   like it should be `.gitignore`d but isn't.

Report the actual output of each command run, not a summary that implies success without
evidence. If a command fails, either fix the underlying issue and re-run, or report the
failure honestly — never report success based solely on code inspection without having run the
verification (`prompt.md` § 62: "Do not declare success based solely on code inspection").
