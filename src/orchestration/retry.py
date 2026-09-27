"""Bounded retry with backoff for every LLM client call (docs/architecture.md
§ 10: "timeouts and bounded retries with exponential backoff on every
external call"; "Malformed model/tool output -> reject and retry with
backoff up to a bound, then escalate").

Only provider/transport-shaped failures are retried — `ValidationError`
(malformed structured output, `.claude/rules/ai-agents.md`: "reject and
retry ... never silently coerce"), `TimeoutError`, `ConnectionError`, and
`OSError` (network-shaped). A real bug (`TypeError`, `KeyError`, ...) is
never caught here — retrying a programming error would silently mask it,
not make the system more reliable.
"""

import time
from collections.abc import Callable

from pydantic import ValidationError

_RETRYABLE_EXCEPTIONS = (ValidationError, TimeoutError, ConnectionError, OSError)
_BACKOFF_SECONDS = 0.05  # deliberately small — real backoff tuning is an operational decision


class LLMUnavailableError(Exception):
    """Raised once an LLM client call has exhausted its retry budget — caught
    at the top of `flow.run_case()` to switch the whole case to the
    deterministic fallback path (`src/orchestration/fallback.py`,
    `docs/demo-script.md` Scenario E)."""


def call_with_retry[T](
    fn: Callable[..., T], *args: object, max_attempts: int, **kwargs: object
) -> T:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < max_attempts:
                time.sleep(_BACKOFF_SECONDS * attempt)
    raise LLMUnavailableError(
        f"{getattr(fn, '__qualname__', fn)!r} failed after {max_attempts} attempt(s)"
    ) from last_exc
