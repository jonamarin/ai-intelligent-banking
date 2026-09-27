"""Tests for src/api/cases.py — offline, using an in-memory SQLite engine
via dependency override (same pattern as tests/unit/conftest.py's
`db_session` fixture, but here at the Engine level since the API layer
uses raw Core queries, not ORM sessions).

Full create-a-case / review-a-case round trips against real evidence-graph
construction need a real Postgres (`src/policies/gateway.py`,
`src/evidence/persist.py` before it, have no offline unit test either) —
verified live instead, in a real browser
(`.claude/rules/frontend.md`: "start the dev server and exercise the golden
path... in a real browser") and via curl; see `src/api/README.md` for that
verification record. What's tested here is everything that doesn't need
evidence-graph construction: role-gating, request validation, and 404s.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from src.api.deps import get_db_engine
from src.api.main import create_app
from src.models import Base


@pytest.fixture
def sqlite_engine() -> Generator[Engine, None, None]:
    # StaticPool: the API layer opens/closes a connection per query
    # (`with engine.connect() as conn: ...`), and a plain sqlite:///:memory:
    # engine hands out a *fresh, empty* in-memory database on every new
    # connection — StaticPool keeps them all on the one real connection so
    # tables created here are still there for the API's own queries.
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(sqlite_engine: Engine) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_engine] = lambda: sqlite_engine
    return TestClient(app)


def test_session_endpoint_sets_role_cookie(client: TestClient) -> None:
    response = client.post("/api/v1/cases/session", json={"role": "analyst"})
    assert response.status_code == 200
    assert response.json() == {"role": "analyst"}
    assert response.cookies.get("role") == "analyst"


def test_session_endpoint_rejects_invalid_role(client: TestClient) -> None:
    response = client.post("/api/v1/cases/session", json={"role": "admin"})
    assert response.status_code == 422


def test_session_endpoint_rejects_extra_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/cases/session", json={"role": "analyst", "is_super_admin": True}
    )
    assert response.status_code == 422


def test_list_cases_requires_analyst_role_by_default_customer_session(client: TestClient) -> None:
    """No session cookie set -> defaults to "customer" (src/api/deps.py) ->
    403, never reaching the engine at all."""
    response = client.get("/api/v1/cases")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "unauthorized"


def test_list_cases_allowed_for_analyst_role(client: TestClient) -> None:
    client.cookies.set("role", "analyst")
    response = client.get("/api/v1/cases")
    assert response.status_code == 200
    assert response.json() == []


def test_list_cases_allowed_for_supervisor_role(client: TestClient) -> None:
    client.cookies.set("role", "supervisor")
    response = client.get("/api/v1/cases")
    assert response.status_code == 200


def test_review_requires_analyst_role_even_for_a_nonexistent_case(client: TestClient) -> None:
    """The role check must run before any DB lookup — a customer session
    gets 403 for a case that doesn't even exist, not a 404 that would leak
    whether the case_id is valid."""
    response = client.post(
        "/api/v1/cases/DOES-NOT-EXIST/review",
        json={"reviewer_id": "CUST-1", "action": "approve"},
    )
    assert response.status_code == 403


def test_review_rejects_malformed_action(client: TestClient) -> None:
    client.cookies.set("role", "analyst")
    response = client.post(
        "/api/v1/cases/DOES-NOT-EXIST/review",
        json={"reviewer_id": "A-1", "action": "delete"},
    )
    assert response.status_code == 422


def test_get_case_not_found_returns_404(client: TestClient) -> None:
    client.cookies.set("role", "analyst")
    response = client.get("/api/v1/cases/DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_case_not_found_for_customer_role_too(client: TestClient) -> None:
    response = client.get("/api/v1/cases/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_create_case_request_rejects_extra_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/cases", json={"transaction_id": "TRX-1", "amount": 999999}
    )
    assert response.status_code == 422


def test_create_case_request_rejects_missing_transaction_id(client: TestClient) -> None:
    response = client.post("/api/v1/cases", json={})
    assert response.status_code == 422


def test_ui_home_page_renders(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Start or open a case" in response.text


def test_ui_analyst_queue_requires_reviewer_role(client: TestClient) -> None:
    """The UI route enforces the same 403 the JSON API does — not just a
    hidden link (`.claude/rules/frontend.md`)."""
    response = client.get("/analyst/cases")
    assert response.status_code == 403


def test_ui_analyst_queue_renders_for_analyst_role(client: TestClient) -> None:
    client.cookies.set("role", "analyst")
    response = client.get("/analyst/cases")
    assert response.status_code == 200
    assert "review queue" in response.text.lower()


def test_ui_customer_case_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/customer/cases/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_ui_role_switch_sets_cookie_and_redirects(client: TestClient) -> None:
    response = client.get("/session/analyst", follow_redirects=False)
    assert response.status_code == 303
    assert response.cookies.get("role") == "analyst"


def test_ui_role_switch_falls_back_to_default_for_unknown_role(client: TestClient) -> None:
    response = client.get("/session/superadmin", follow_redirects=False)
    assert response.status_code == 303
    assert response.cookies.get("role") == "customer"
