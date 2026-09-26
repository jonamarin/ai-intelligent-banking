# Claude Code Hooks

Two `PreToolUse` hooks provide a deterministic backstop for two of the safety requirements in
`CLAUDE.md` § 7 and `.claude/rules/security.md`. **They are a backstop, not the full
enforcement model** — see `docs/guardrails.md` § 1 for why prompt/rule/skill instructions
alone are never sufficient, and note that these two scripts are narrow, tested heuristics, not
a complete data-loss-prevention or command-sandboxing system.

Both hooks were manually tested before being wired into `.claude/settings.json` (see
§ Validation performed below) — this is not a theoretical control.

## protect_sensitive_files.py

**Blocks:** `Read`/`Edit`/`Write`/`NotebookEdit` tool calls whose `file_path` (or
`notebook_path`/`path`) matches a secret-bearing filename pattern: `.env` and `.env.<suffix>`
(but not `.env.example`/`.env.sample`/`.env.template`), `*.pem`, `*.key`, `id_rsa*`,
`id_ed25519*`, `credentials.json`, `.aws/credentials`, `.npmrc`, `*service*account*.json`.

**Allows:** everything else, including `.env.example` explicitly.

**Limitations:**
- Pattern-based, not exhaustive — a secret in an unexpectedly-named file is not caught.
- Only inspects the tool's file-path-like input field, not file *contents* — a secret
  accidentally placed in an otherwise-normal file is not caught by this hook (that's what the
  final-response secret scan in the repository-initialization validation step, and ordinary
  code review, are for).
- Requires `python` on `PATH`. If unavailable, the hook command fails to run and Claude Code
  does not block the tool call — this hook **fails open** in that case, silently. There is no
  portable way around this without assuming a specific interpreter is installed; Python was
  chosen because it's this project's confirmed backend language (`docs/architecture.md` § 5)
  and was verified present on the development machine used to author this repository.

## guard_dangerous_commands.py

**Blocks:** `Bash` tool calls whose `command` matches a short, high-confidence list of
destructive patterns: `rm -rf /`, `rm -rf ~`, `git push --force`/`-f`, `git branch -D`,
`DROP DATABASE`, `DROP TABLE`, `TRUNCATE TABLE`, `terraform destroy`, `terraform apply`
(blocked unconditionally — no infrastructure/production target exists in this repository at
all yet), `docker system prune -f`, an AWS CLI `delete`-style command, and `--no-verify`.

**Allows:** everything else, including ordinary `rm -rf <relative-path>` (e.g.,
`rm -rf node_modules`), `git status`, `git push` without `--force`, and normal `git reset`/
`git checkout` usage — the hook deliberately does not try to guess intent for commands that are
routine in normal development and only risky in specific circumstances Claude Code's own
Git Safety Protocol already governs via user confirmation.

**Limitations:**
- Regex pattern matching on shell text is inherently evadable (quoting, variable expansion,
  command substitution, encoding) and does not understand full shell semantics. This is a
  backstop against obvious/accidental destructive commands, not a sandbox.
- Only covers the `Bash` tool. This repository's `PowerShell` tool is a distinct `tool_name`
  and is **not currently covered** — extending coverage there is documented here as a gap, not
  silently assumed to be covered.
- Same Python-on-`PATH` fail-open caveat as above.

## What these hooks do not block

Anything not matching the specific patterns above — including most git operations, most file
operations, database migrations that aren't a bare `DROP`/`TRUNCATE`, and any destructive
action taken through a tool other than `Bash`/`Read`/`Edit`/`Write`/`NotebookEdit`. They do not
replace: Claude Code's own confirmation prompts for actions outside the current permission
mode, the Git Safety Protocol in the system prompt, or human review of risky changes.

## Configuration

Wired via `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Edit|Write|NotebookEdit",
        "hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect_sensitive_files.py\""}]
      },
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard_dangerous_commands.py\""}]
      }
    ]
  }
}
```

## Validation performed

Both scripts were run manually (not just read) with representative JSON payloads on stdin
before being wired into `settings.json`:

- `protect_sensitive_files.py`: `.env` → blocked; `.env.example` → allowed; a normal doc file
  → allowed; an SSH private key path → blocked.
- `guard_dangerous_commands.py`: `rm -rf /` → blocked; `git push --force origin main` →
  blocked; `git status` → allowed; `rm -rf node_modules` → allowed (not a root/home delete);
  `terraform apply -auto-approve` → blocked.

**Confirmed live in a real session (2026-09-25):** after wiring these into
`.claude/settings.json`, a Bash tool call whose command text contained the substring
`terraform apply` (inside a test payload, not an actual invocation) was blocked by Claude
Code's own `PreToolUse` hook dispatch — i.e., `guard_dangerous_commands.py` is not just a
script that behaves correctly standalone, it demonstrably intercepts real tool calls in this
harness. One side effect worth knowing: this means a trigger phrase appearing anywhere in a
Bash command's text — even inside an echoed string meant only to test the hook itself — will
also block that outer command. Test hook logic by invoking the script directly with a crafted
stdin payload in isolation (as below) rather than trying to provoke it through a live tool call
a second time.

Re-run these checks after editing either script, before trusting the change:

```
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python .claude/hooks/protect_sensitive_files.py
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python .claude/hooks/guard_dangerous_commands.py
```

A block prints a `permissionDecision: deny` JSON object; an allow prints nothing.
