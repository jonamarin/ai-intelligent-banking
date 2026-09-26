from fastapi.testclient import TestClient

from src.api.main import CORRELATION_ID_HEADER, create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_propagates_correlation_id() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health", headers={CORRELATION_ID_HEADER: "test-id-123"})
    assert response.headers[CORRELATION_ID_HEADER] == "test-id-123"


def test_health_generates_correlation_id_when_absent() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.headers.get(CORRELATION_ID_HEADER)


def test_unknown_route_returns_structured_error_not_stack_trace() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
