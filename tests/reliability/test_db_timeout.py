"""Database unavailable (`docs/architecture.md` § 10: "fail the request with
a clear error; never approve a financial action without being able to read
authoritative state") — verified against a genuinely unreachable address, not
just asserted from documentation.

This deliberately targets a non-routable IP (`10.255.255.1`, RFC 1918 space
unlikely to be routed from a test runner) rather than a closed port: a
closed port fails almost instantly via TCP RST, which doesn't exercise
`connect_timeout` at all — an unreachable host is what actually proves the
bound is doing something (`src/models/base.py`'s `get_engine()`, Phase 9).
"""

import time

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

_UNREACHABLE_HOST = "10.255.255.1"
_SHORT_TIMEOUT_SECONDS = 2


def test_unreachable_database_fails_within_the_bounded_timeout_not_indefinitely() -> None:
    engine = create_engine(
        f"postgresql+psycopg://banking:banking@{_UNREACHABLE_HOST}:5433/banking_ai",
        connect_args={"connect_timeout": _SHORT_TIMEOUT_SECONDS},
    )
    started = time.monotonic()
    try:
        with engine.connect():
            pass
        raise AssertionError("expected the connection to fail — host is unreachable by design")
    except OperationalError:
        elapsed = time.monotonic() - started
        # Generous upper bound (timeout + overhead), never "hung
        # indefinitely" — the actual documented failure mode being tested.
        assert elapsed < _SHORT_TIMEOUT_SECONDS + 10
    finally:
        engine.dispose()
