from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, LoginAttempt, SessionToken, User
from app.auth.security import token_hash, verify_password
from app.config import get_settings
from app.courses.models import Class, ClassMember, Course
from app.deps import class_role, require_class_lecturer, require_class_member
from app.seed import seed

CSRF = {"X-DUT-CSRF": "1"}
PASSWORD = "dutlearn-test-password"


@pytest.fixture
def auth_db(test_engine: Engine, monkeypatch):
    monkeypatch.setenv("DUT_COOKIE_SECURE", "false")
    monkeypatch.setenv("DUT_SESSION_TTL_HOURS", "12")
    monkeypatch.setenv("DUT_SEED_PASSWORD", PASSWORD)
    get_settings.cache_clear()
    with Session(test_engine) as db:
        db.execute(
            text(
                "TRUNCATE login_attempts, audit_events, sessions, class_members, "
                "classes, courses, users CASCADE"
            )
        )
        db.commit()
        seed(db)
        yield db
    get_settings.cache_clear()


def login(client: TestClient, account: str = "sv1", password: str = PASSWORD):
    return client.post(
        "/api/auth/login",
        headers=CSRF,
        json={"email": f"{account}@dutlearn.local", "password": password},
    )


def class_id(db: Session, code: str = "KTLT-01") -> str:
    return str(db.scalars(select(Class).where(Class.code == code)).one().id)


def test_login_cookie_and_hash(db_client: TestClient, auth_db: Session):
    response = db_client.post(
        "/api/auth/login", headers=CSRF, json={"email": "SV1@DUTLEARN.LOCAL", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "sv1@dutlearn.local"
    assert {"class_id", "class_code", "course_code", "course_name", "role"} == set(
        response.json()["classes"][0]
    )
    assert "password_hash" not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert "Max-Age=43200" in cookie and "Secure" not in cookie
    raw = db_client.cookies["dut_session"]
    stored = auth_db.scalars(select(SessionToken)).one()
    assert stored.token_hash == token_hash(raw) and stored.token_hash != raw
    assert len(stored.token_hash) == 64
    assert db_client.get("/api/auth/me").json() == response.json()
    assert response.headers["X-Request-ID"]


def test_secure_cookie_and_ttl(db_client: TestClient, auth_db: Session, monkeypatch):
    monkeypatch.setenv("DUT_COOKIE_SECURE", "true")
    monkeypatch.setenv("DUT_SESSION_TTL_HOURS", "2")
    get_settings.cache_clear()
    response = login(db_client)
    assert "Secure" in response.headers["set-cookie"]
    assert "Max-Age=7200" in response.headers["set-cookie"]
    stored = auth_db.scalars(select(SessionToken)).one()
    assert 7190 < (stored.expires_at - datetime.now(UTC)).total_seconds() <= 7200


def test_credentials_do_not_disclose_account(db_client: TestClient, auth_db: Session):
    known = login(db_client, password="wrong")
    unknown = login(db_client, account="unknown", password="wrong")
    assert known.status_code == unknown.status_code == 401
    for field in ["code", "message", "details"]:
        assert known.json()["error"][field] == unknown.json()["error"][field]
    assert known.json()["error"]["details"] == {"attempts_remaining": 4}
    assert known.json()["error"]["code"] == "invalid_credentials"
    assert auth_db.scalar(select(func.count()).select_from(LoginAttempt)) == 2


@pytest.mark.parametrize("account", ["sv1", "unknown"])
def test_rate_limit(db_client: TestClient, auth_db: Session, account: str):
    remaining = []
    for _ in range(5):
        failed = login(db_client, account, "wrong")
        assert failed.status_code == 401
        remaining.append(failed.json()["error"]["details"]["attempts_remaining"])
    assert remaining == [4, 3, 2, 1, 0]
    response = login(db_client, account)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_attempts"
    assert 0 < response.json()["error"]["details"]["retry_after_seconds"] <= 900
    # A different email is not blocked; then the rolling window expires.
    assert login(db_client, "gv1").status_code == 200
    auth_db.execute(text("UPDATE login_attempts SET attempted_at = now() - interval '16 minutes'"))
    auth_db.commit()
    assert login(db_client, account).status_code == (200 if account == "sv1" else 401)


@pytest.mark.parametrize("state", ["expired", "revoked", "inactive", "invalid_token"])
def test_session_rejected(db_client: TestClient, auth_db: Session, state: str):
    assert login(db_client).status_code == 200
    stored = auth_db.scalars(select(SessionToken)).one()
    if state == "expired":
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif state == "revoked":
        stored.revoked_at = datetime.now(UTC)
    elif state == "inactive":
        auth_db.get(User, stored.user_id).is_active = False
    else:
        db_client.cookies.set("dut_session", "invalid")
    auth_db.commit()
    response = db_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_logout_revokes_cookie(db_client: TestClient, auth_db: Session):
    login(db_client)
    raw = db_client.cookies["dut_session"]
    response = db_client.post("/api/auth/logout", headers=CSRF)
    assert response.status_code == 204 and response.content == b""
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "dut_session" not in db_client.cookies
    db_client.cookies.set("dut_session", raw)
    assert db_client.get("/api/auth/me").status_code == 401
    assert auth_db.scalars(select(SessionToken)).one().revoked_at is not None


def test_inactive_login(db_client: TestClient, auth_db: Session):
    user = auth_db.scalars(select(User).where(User.email == "sv1@dutlearn.local")).one()
    user.is_active = False
    auth_db.commit()
    assert login(db_client).json()["error"]["code"] == "invalid_credentials"


@pytest.mark.parametrize("account", [None, "admin", "gv1", "sv1", "sv3"])
def test_permission_matrix(db_client: TestClient, auth_db: Session, account: str | None):
    cid = class_id(auth_db)
    if account:
        assert login(db_client, account).status_code == 200
    admin_status = 401 if account is None else (200 if account == "admin" else 403)
    for path in ["users", "courses", "classes", f"classes/{cid}/members"]:
        assert db_client.get(f"/api/admin/{path}").status_code == admin_status
    response = db_client.get("/api/classes")
    assert response.status_code == (401 if account is None else 200)
    if account:
        expected = [] if account == "admin" else ["KTLT-02" if account == "sv3" else "KTLT-01"]
        assert [c["code"] for c in response.json()] == expected
    expected_status = 401 if account is None else (200 if account in {"gv1", "sv1"} else 404)
    assert db_client.get(f"/api/classes/{cid}").status_code == expected_status
    if account in {"gv1", "sv1"}:
        assert db_client.get(f"/api/classes/{class_id(auth_db, 'KTLT-02')}").status_code == 404
    assert db_client.get(f"/api/classes/{uuid4()}").status_code == (401 if account is None else 404)


@pytest.mark.parametrize("account,status", [("sv1", 404), ("gv1", 200), ("admin", 404)])
def test_closed_class(db_client: TestClient, auth_db: Session, account: str, status: int):
    login(db_client, account)
    assert db_client.get(f"/api/classes/{class_id(auth_db, 'KTLT-CLOSED')}").status_code == status


def test_shared_lecturer_policy(auth_db: Session):
    classroom = auth_db.scalars(select(Class).where(Class.code == "KTLT-01")).one()
    for account, expected in [("gv1", None), ("sv1", 403), ("gv2", 404), ("admin", 404)]:
        user = auth_db.scalars(select(User).where(User.email == f"{account}@dutlearn.local")).one()
        assert class_role(auth_db, user, classroom.id) == (
            "lecturer" if account == "gv1" else "student" if account == "sv1" else None
        )
        if expected:
            with pytest.raises(HTTPException) as exc:
                member_class = require_class_member(classroom.id, auth_db, user)
                require_class_lecturer(member_class, auth_db, user)
            assert exc.value.status_code == expected
        else:
            member_class = require_class_member(classroom.id, auth_db, user)
            assert require_class_lecturer(member_class, auth_db, user).id == classroom.id


@pytest.mark.parametrize("account", [None, "sv1", "gv1"])
def test_admin_writes_forbidden(db_client: TestClient, auth_db: Session, account: str | None):
    if account:
        login(db_client, account)
    cid = class_id(auth_db)
    user_id = str(auth_db.scalars(select(User.id)).first())
    requests = [
        ("/users", {"email": "new@example.com", "full_name": "New", "password": PASSWORD}),
        ("/courses", {"code": "NEW", "name": "New"}),
        (
            "/classes",
            {
                "course_id": str(auth_db.scalars(select(Course.id)).one()),
                "code": "NEW",
                "term": "test",
            },
        ),
        (f"/classes/{cid}/members", {"user_id": user_id, "role": "student"}),
    ]
    for path, payload in requests:
        assert db_client.post("/api/admin" + path, json=payload, headers=CSRF).status_code == (
            401 if account is None else 403
        )
    assert db_client.delete(
        f"/api/admin/classes/{cid}/members/{user_id}", headers=CSRF
    ).status_code == (401 if account is None else 403)


def test_admin_crud_audited(db_client: TestClient, auth_db: Session):
    login(db_client, "admin")
    user_payload = {"email": "NEW@EXAMPLE.COM", "password": PASSWORD, "full_name": "New"}
    user = db_client.post("/api/admin/users", headers=CSRF, json=user_payload)
    assert user.status_code == 201 and user.json()["email"] == "new@example.com"
    assert "password" not in user.text
    assert db_client.post("/api/admin/users", headers=CSRF, json=user_payload).status_code == 409
    course = db_client.post(
        "/api/admin/courses", headers=CSRF, json={"code": "NEW", "name": "New course"}
    )
    assert course.status_code == 201
    classroom = db_client.post(
        "/api/admin/classes",
        headers=CSRF,
        json={"course_id": course.json()["id"], "code": "NEW-01", "term": "1"},
    )
    assert classroom.status_code == 201 and classroom.json()["content_version"] == 0
    cid = classroom.json()["id"]
    uid = user.json()["id"]
    payload = {"user_id": uid, "role": "student"}
    member = db_client.post(f"/api/admin/classes/{cid}/members", headers=CSRF, json=payload)
    assert member.status_code == 201
    assert (
        db_client.post(f"/api/admin/classes/{cid}/members", headers=CSRF, json=payload).status_code
        == 409
    )
    assert db_client.get(f"/api/admin/classes/{cid}/members").json() == [member.json()]
    assert (
        db_client.delete(f"/api/admin/classes/{cid}/members/{uid}", headers=CSRF).status_code == 204
    )
    events = list(auth_db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))
    assert len(events) == 5
    assert [e.action for e in events].count("create") == 4
    assert [e.action for e in events].count("delete") == 1
    assert all(
        e.actor_id
        == auth_db.scalars(select(User.id).where(User.email == "admin@dutlearn.local")).one()
        for e in events
    )
    assert all("password" not in str(e.detail) for e in events)
    db_client.cookies.clear()
    assert (
        db_client.post(
            "/api/auth/login", headers=CSRF, json={"email": "new@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_membership_removal_takes_effect(db_client: TestClient, auth_db: Session):
    login(db_client)
    cid = class_id(auth_db)
    member = auth_db.scalars(
        select(ClassMember).where(
            ClassMember.class_id == cid,
            ClassMember.user_id
            == auth_db.scalars(select(User.id).where(User.email == "sv1@dutlearn.local")).one(),
        )
    ).one()
    auth_db.delete(member)
    auth_db.commit()
    assert db_client.get(f"/api/classes/{cid}").status_code == 404


def test_csrf_on_auth_and_admin(db_client: TestClient, auth_db: Session):
    assert (
        db_client.post(
            "/api/auth/login", json={"email": "sv1@dutlearn.local", "password": PASSWORD}
        ).status_code
        == 403
    )
    login(db_client, "admin")
    for path in ["/api/auth/logout", "/api/admin/courses"]:
        response = db_client.post(path, json={"code": "NEW", "name": "New"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_required"
    assert db_client.delete(f"/api/admin/classes/{uuid4()}/members/{uuid4()}").status_code == 403


def test_seed_idempotent(auth_db: Session):
    def counts():
        return [
            auth_db.scalar(select(func.count()).select_from(model))
            for model in [User, Course, Class, ClassMember]
        ]

    before = counts()
    hashes = list(auth_db.scalars(select(User.password_hash).order_by(User.email)))
    seed(auth_db)
    assert before == counts() == [7, 1, 3, 8]
    assert hashes == list(auth_db.scalars(select(User.password_hash).order_by(User.email)))
    assert all(h.startswith("$argon2") and verify_password(PASSWORD, h) for h in hashes)
    assert auth_db.scalars(select(Class).where(Class.status == "closed")).one()


def test_migration_constraints(test_engine: Engine):
    inspector = inspect(test_engine)
    assert {"courses", "classes", "class_members", "audit_events", "login_attempts"} <= set(
        inspector.get_table_names()
    )
    assert "ix_sessions_user_id" in {i["name"] for i in inspector.get_indexes("sessions")}
    assert "ix_class_members_user_id" in {i["name"] for i in inspector.get_indexes("class_members")}
    assert any(
        c["column_names"] == ["class_id", "user_id"]
        for c in inspector.get_unique_constraints("class_members")
    )
    assert any(
        c["name"] == "ck_class_members_role"
        for c in inspector.get_check_constraints("class_members")
    )
    assert any(c["name"] == "ck_classes_status" for c in inspector.get_check_constraints("classes"))


def test_concurrent_login_limit(test_engine: Engine, auth_db: Session):
    from app.auth.service import login as login_service
    from app.errors import APIError

    def attempt():
        with Session(test_engine) as db:
            try:
                login_service(db, "sv1@dutlearn.local", "wrong", "concurrency-test")
            except APIError as exc:
                return exc.status_code
        return 200

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(lambda _: attempt(), range(6)))
    assert sorted(statuses) == [401, 401, 401, 401, 401, 429]
    assert auth_db.scalar(select(func.count()).select_from(LoginAttempt)) == 5


def test_admin_invalid_references(db_client: TestClient, auth_db: Session):
    login(db_client, "admin")
    response = db_client.post(
        "/api/admin/classes",
        headers=CSRF,
        json={"course_id": str(uuid4()), "code": "X", "term": "1"},
    )
    assert response.status_code == 404
    cid = class_id(auth_db)
    response = db_client.post(
        f"/api/admin/classes/{cid}/members",
        headers=CSRF,
        json={"user_id": str(uuid4()), "role": "student"},
    )
    assert response.status_code == 404
    response = db_client.post(
        f"/api/admin/classes/{cid}/members",
        headers=CSRF,
        json={"user_id": str(uuid4()), "role": "admin"},
    )
    assert response.status_code == 422
    assert auth_db.scalar(select(func.count()).select_from(AuditEvent)) == 0
