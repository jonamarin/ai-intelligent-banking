"""Request-scoped dependencies for the API layer (Phase 10).

`get_current_role`/`require_reviewer_role`: **not** a real authentication
system — `docs/security-model.md` § 3 explicitly puts building one out of
scope for this prototype ("use a trusted test session/identity
abstraction"). A `role` cookie, set by `POST /api/v1/session` (never a
client-supplied request body field, so at least the *shape* of "derive
authorization from session context, not request data" holds —
`.claude/rules/backend.md`), stands in for it. This is honestly surfaced
everywhere it's used, in the UI and in this docstring, not disguised as real
auth.
"""

from typing import Literal

from fastapi import Request
from sqlalchemy.engine import Engine

from src.api.errors import UnauthorizedError
from src.models.base import get_engine

Role = Literal["customer", "analyst", "supervisor"]

ROLE_COOKIE = "role"
DEFAULT_ROLE: Role = "customer"
_VALID_ROLES: tuple[Role, ...] = ("customer", "analyst", "supervisor")


def get_db_engine() -> Engine:
    return get_engine()


def get_current_role(request: Request) -> Role:
    value = request.cookies.get(ROLE_COOKIE, DEFAULT_ROLE)
    if value in _VALID_ROLES:
        return value  # type: ignore[return-value]
    return DEFAULT_ROLE


def require_reviewer_role(request: Request) -> Role:
    """Gates every human-review/approval endpoint
    (`.claude/rules/frontend.md`: "Human-review/approval controls are only
    rendered for an authenticated analyst/supervisor session — never
    conditionally hidden-but-reachable for a customer session") — enforced
    here, server-side, not just hidden in the UI."""
    role = get_current_role(request)
    if role not in ("analyst", "supervisor"):
        raise UnauthorizedError("This action requires an analyst or supervisor session.")
    return role
