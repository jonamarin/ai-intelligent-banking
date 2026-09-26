#!/usr/bin/env python3
"""PreToolUse hook: block obviously destructive shell commands.

Reads the Claude Code hook JSON payload from stdin, checks tool_input.command
(for the Bash tool) against a small, conservative set of high-confidence
destructive patterns, and denies the tool call if it matches.

Limitations (see .claude/hooks/README.md):
- Pattern matching on shell text is inherently incomplete: it can be evaded
  (quoting, variable expansion, encoding) and cannot understand full shell
  semantics. This is a backstop against obvious/accidental destructive
  commands, not a sandbox and not a substitute for reviewing risky commands.
- Only recognizes the patterns in DANGEROUS_PATTERNS below.
- Requires `python` to be resolvable on PATH; if it is not, the hook command
  itself fails and Claude Code does not block the tool call (fails open).
- Does not inspect PowerShell tool commands (this repo's PowerShell tool is a
  separate tool_name); extending coverage there is future work, noted in
  .claude/hooks/README.md rather than claimed as covered.
"""
import json
import re
import sys

# (pattern, human-readable reason) — matched against the raw command string.
# Kept deliberately short and high-confidence to avoid blocking normal
# development work (the master prompt requires: "do not block normal
# repository development").
DANGEROUS_PATTERNS = [
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(\s|$)", "rm -rf against filesystem root"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+~(\s|/|$)", "rm -rf against the home directory"),
    (r"\bgit\s+push\s+.*--force(\s|$)", "force-push (can overwrite remote/shared history)"),
    (r"\bgit\s+push\s+.*\s-f(\s|$)", "force-push (can overwrite remote/shared history)"),
    (r"\bgit\s+branch\s+-D\b", "force-delete a git branch"),
    (r"\bdrop\s+database\b", "DROP DATABASE"),
    (r"\bdrop\s+table\b", "DROP TABLE"),
    (r"\btruncate\s+table\b", "TRUNCATE TABLE"),
    (r"\bterraform\s+destroy\b", "terraform destroy"),
    (r"\bterraform\s+apply\b", "terraform apply (no infra/production target exists in this repo)"),
    (r"\bdocker\s+system\s+prune\b.*-f\b", "docker system prune -f (destructive, unattended)"),
    (r"\baws\s+.*\bdelete\b", "AWS CLI delete-style command"),
    (r"--no-verify\b", "bypassing git hooks with --no-verify"),
]

COMPILED = [(re.compile(p, re.IGNORECASE), reason) for p, reason in DANGEROUS_PATTERNS]


def find_violation(command: str):
    for pattern, reason in COMPILED:
        if pattern.search(command):
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    command = tool_input.get("command")
    if not command:
        return 0

    reason = find_violation(str(command))
    if reason:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Blocked by guard_dangerous_commands hook: command matches a "
                    f"high-risk pattern ({reason}). See .claude/hooks/README.md. "
                    "If this action is actually intended and authorized, ask the "
                    "user to run it manually or explicitly confirm before retrying."
                ),
            }
        }
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
