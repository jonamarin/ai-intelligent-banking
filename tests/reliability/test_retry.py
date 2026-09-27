"""Tests for src/orchestration/retry.py — offline, no DB, no API key."""

import pytest

from src.agents.schemas import IntentResult
from src.orchestration.retry import LLMUnavailableError, call_with_retry


def test_succeeds_on_first_attempt_without_retrying() -> None:
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        return "ok"

    assert call_with_retry(fn, max_attempts=3) == "ok"
    assert len(calls) == 1


def test_retries_after_a_transient_failure_then_succeeds() -> None:
    """docs/architecture.md § 10: bounded retries — this proves the retry
    budget genuinely retries, not just that fallback triggers on any
    failure."""
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        if len(calls) < 2:
            raise TimeoutError("transient")
        return "ok"

    assert call_with_retry(fn, max_attempts=3) == "ok"
    assert len(calls) == 2


def test_raises_llm_unavailable_error_after_exhausting_attempts() -> None:
    def fn() -> str:
        raise TimeoutError("permanently down")

    with pytest.raises(LLMUnavailableError):
        call_with_retry(fn, max_attempts=2)


def test_validation_error_is_retryable() -> None:
    """docs/architecture.md § 10: "Malformed model/tool output -> reject and
    retry with backoff up to a bound, then escalate" — a ValidationError
    (the shape a real provider's malformed structured output would raise)
    is treated the same as a transport failure."""

    def fn() -> IntentResult:
        return IntentResult(intent="not_a_real_intent", confidence=0.5)  # type: ignore[arg-type]

    with pytest.raises(LLMUnavailableError):
        call_with_retry(fn, max_attempts=2)


def test_a_programming_bug_is_never_silently_retried_or_masked() -> None:
    """TypeError/KeyError/etc. are real bugs, not provider failures —
    retrying (or falling back) would mask them instead of surfacing them."""

    def fn() -> str:
        raise KeyError("not a provider failure")

    with pytest.raises(KeyError):
        call_with_retry(fn, max_attempts=3)


def test_max_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        call_with_retry(lambda: None, max_attempts=0)
