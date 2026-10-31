import httpx
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def test_health_real_db(db_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **kw: httpx.Response(200, json={"version": "test"})
    )
    response = db_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "llm": True}
    assert response.headers["X-Request-ID"]


def test_llm_unavailable(db_client: TestClient, monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", unavailable)
    assert db_client.get("/api/health").json() == {"status": "ok", "db": True, "llm": False}


def test_initial_schema(test_engine: Engine) -> None:
    with test_engine.begin() as connection:
        assert {"users", "sessions"} <= set(inspect(connection).get_table_names())
        user_id = connection.execute(
            text(
                "INSERT INTO users (email, full_name, password_hash) "
                "VALUES ('test@example.com', 'Test', 'hash') RETURNING id"
            )
        ).scalar_one()
        assert user_id.version == 4
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
