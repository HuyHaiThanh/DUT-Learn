from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


def test_not_found(client: TestClient) -> None:
    response = client.get("/api/missing")
    assert response.status_code == 404
    error = response.json()["error"]
    assert set(error) == {"code", "message", "request_id"}
    assert error["code"] == "not_found"
    assert error["message"] == "Không tìm thấy tài nguyên."
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_csrf_required(client: TestClient) -> None:
    response = client.post("/api/missing")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_required"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_method_not_allowed(client: TestClient) -> None:
    response = client.post("/api/health", headers={"X-DUT-CSRF": "1"})
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in response.headers["allow"]


def test_internal_error_hides_details(client: TestClient) -> None:
    def broken_dependency() -> None:
        raise RuntimeError("private database connection details")

    app.dependency_overrides[get_db] = broken_dependency
    try:
        response = client.get("/api/health")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
        assert "private" not in response.text
    finally:
        app.dependency_overrides.clear()
