#!/usr/bin/env python3
"""PreToolUse hook: block Read/Edit/Write/NotebookEdit on secret-bearing files.

Reads the Claude Code hook JSON payload from stdin, checks tool_input.file_path
(or .notebook_path) against a small, conservative blocklist of secret-bearing
filename patterns, and denies the tool call if it matches.

Limitations (see .claude/hooks/README.md):
- Only recognizes patterns in this file's PATTERNS list; anything not matching
  is allowed through. This is a backstop, not a complete DLP solution.
- Only inspects the file_path/notebook_path field of the tool input.
- Requires `python` to be resolvable on PATH; if it is not, the hook command
  itself fails and Claude Code does not block the tool call (fails open).
"""
import json
import re
import sys

# Filenames/patterns that must never be opened by Claude Code tools.
# Deliberately conservative: false negatives are safer to accept than
# false positives that would block normal repository development.
BLOCKED_PATTERNS = [
    r"(^|[\\/])\.env$",
    r"(^|[\\/])\.env\.[^.]+$",  # .env.local, .env.production, etc.
    r"\.pem$",
    r"\.key$",
    r"(^|[\\/])id_rsa(\.[^\\/]+)?$",
    r"(^|[\\/])id_ed25519(\.[^\\/]+)?$",
    r"credentials\.json$",
    r"(^|[\\/])\.aws[\\/]credentials$",
    r"(^|[\\/])\.npmrc$",
    r"service[-_]?account.*\.json$",
]

# Explicit allowlist: names that would otherwise match a pattern above but
# are safe, committed example/template files.
ALLOWED_EXACT_SUFFIXES = [
    ".env.example",
    ".env.sample",
    ".env.template",
]

BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


def is_blocked(path: str) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/")
    for suffix in ALLOWED_EXACT_SUFFIXES:
        if normalized.lower().endswith(suffix):
            return False
    return any(r.search(normalized) for r in BLOCKED_RE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # can't parse -> don't block; fail open on malformed input

    tool_input = payload.get("tool_input", {}) or {}
    candidate_paths = [
        tool_input.get("file_path"),
        tool_input.get("notebook_path"),
        tool_input.get("path"),
    ]

    for path in candidate_paths:
        if path and is_blocked(str(path)):
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked by protect_sensitive_files hook: '{path}' matches a "
                        "secret-bearing file pattern. See .claude/hooks/README.md. "
                        "If this file is actually safe to open, ask the user to "
                        "confirm and adjust the hook's allowlist."
                    ),
                }
            }
            print(json.dumps(result))
            return 0

    return 0  # no match -> allow (no decision emitted)


if __name__ == "__main__":
    sys.exit(main())
