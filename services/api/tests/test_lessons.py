from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, SessionToken, User
from app.auth.security import token_hash
from app.courses.models import Class, ClassMember, Course, Lesson
from app.courses.schemas import LessonCreate, LessonUpdate

CSRF = {"X-DUT-CSRF": "1"}


@pytest.fixture
def lesson_data(test_engine: Engine):
    with Session(test_engine) as db:
        course = Course(code=f"T07-{uuid4().hex}", name="Kỹ thuật lập trình")
        db.add(course)
        db.flush()
        classroom = Class(course_id=course.id, code="T07", term="2026-2027.1")
        other = Class(course_id=course.id, code="OTHER", term="2026-2027.1")
        db.add_all([classroom, other])
        db.flush()
        tokens = {}
        actors = {}
        for name, role, target in [
            ("lecturer", "lecturer", classroom),
            ("student", "student", classroom),
            ("other_lecturer", "lecturer", other),
            ("other_student", "student", other),
            ("admin", None, None),
        ]:
            user = User(
                email=f"{uuid4().hex}@example.test",
                full_name=name,
                password_hash="unused",
                system_role="admin" if name == "admin" else "user",
            )
            db.add(user)
            db.flush()
            if role:
                db.add(ClassMember(class_id=target.id, user_id=user.id, role=role))
            token = uuid4().hex
            db.add(
                SessionToken(
                    user_id=user.id,
                    token_hash=token_hash(token),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            tokens[name] = token
            actors[name] = user.id
        published = Lesson(
            class_id=classroom.id,
            title="Đã công bố",
            position=2,
            is_published=True,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        draft = Lesson(class_id=classroom.id, title="Nháp", position=2, is_published=False)
        foreign = Lesson(class_id=other.id, title="Lớp khác", position=0, is_published=True)
        db.add_all([published, draft, foreign])
        db.commit()
        yield db, classroom, published, draft, foreign, tokens, actors


def authenticate(client, data, actor):
    client.cookies.clear()
    if actor:
        client.cookies.set("dut_session", data[5][actor])


@pytest.mark.parametrize(
    "actor,read,write",
    [
        ("lecturer", 200, 200),
        ("student", 200, 403),
        ("other_lecturer", 404, 404),
        ("other_student", 404, 404),
        ("admin", 404, 404),
        (None, 401, 401),
    ],
)
def test_permission_matrix(db_client: TestClient, lesson_data, actor, read, write):
    authenticate(db_client, lesson_data, actor)
    classroom, lesson = lesson_data[1:3]
    assert db_client.get(f"/api/classes/{classroom.id}").status_code == read
    assert db_client.post(
        f"/api/classes/{classroom.id}/lessons", headers=CSRF, json={"title": "Mới"}
    ).status_code == (201 if write == 200 else write)
    assert (
        db_client.patch(
            f"/api/lessons/{lesson.id}", headers=CSRF, json={"title": "Sửa"}
        ).status_code
        == write
    )


@pytest.mark.parametrize(
    "actor", ["lecturer", "student", "other_lecturer", "other_student", "admin", None]
)
def test_csrf_required(db_client, lesson_data, actor):
    authenticate(db_client, lesson_data, actor)
    assert (
        db_client.post(
            f"/api/classes/{lesson_data[1].id}/lessons", json={"title": "Mới"}
        ).status_code
        == 403
    )
    assert (
        db_client.patch(
            f"/api/lessons/{lesson_data[2].id}", json={"is_published": False}
        ).status_code
        == 403
    )


def test_detail_visibility_and_fields(db_client, lesson_data):
    _, classroom, published, draft, *_ = lesson_data
    for actor, expected in [("student", [published.id]), ("lecturer", [published.id, draft.id])]:
        authenticate(db_client, lesson_data, actor)
        response = db_client.get(f"/api/classes/{classroom.id}")
        assert response.status_code == 200
        data = response.json()
        assert {
            "id",
            "course_id",
            "code",
            "term",
            "status",
            "content_version",
            "role",
            "course_code",
            "course_name",
            "lessons",
        } == set(data)
        assert data["role"] == actor and data["course_name"] == "Kỹ thuật lập trình"
        assert [item["id"] for item in data["lessons"]] == [str(i) for i in expected]


def test_foreign_missing_and_closed(db_client, lesson_data):
    db, classroom, lesson, _, foreign, *_ = lesson_data
    authenticate(db_client, lesson_data, "lecturer")
    for lesson_id in [foreign.id, uuid4()]:
        assert (
            db_client.patch(
                f"/api/lessons/{lesson_id}", headers=CSRF, json={"title": "Không được"}
            ).status_code
            == 404
        )
    classroom.status = "closed"
    db.commit()
    authenticate(db_client, lesson_data, "student")
    assert db_client.get(f"/api/classes/{classroom.id}").status_code == 404
    assert (
        db_client.post(
            f"/api/classes/{classroom.id}/lessons", headers=CSRF, json={"title": "Không được"}
        ).status_code
        == 404
    )
    assert (
        db_client.patch(
            f"/api/lessons/{lesson.id}", headers=CSRF, json={"title": "Không được"}
        ).status_code
        == 404
    )
    authenticate(db_client, lesson_data, "lecturer")
    assert db_client.get(f"/api/classes/{classroom.id}").status_code == 200
    assert (
        db_client.post(
            f"/api/classes/{classroom.id}/lessons", headers=CSRF, json={"title": "Lớp đóng"}
        ).status_code
        == 201
    )
    assert (
        db_client.patch(
            f"/api/lessons/{lesson.id}", headers=CSRF, json={"title": "Vẫn sửa"}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "a" * 201},
        {"title": None},
        {"title": "X", "position": -1},
    ],
)
def test_validation(db_client, lesson_data, body):
    authenticate(db_client, lesson_data, "lecturer")
    assert (
        db_client.post(
            f"/api/classes/{lesson_data[1].id}/lessons", headers=CSRF, json=body
        ).status_code
        == 422
    )
    assert (
        db_client.patch(f"/api/lessons/{lesson_data[2].id}", headers=CSRF, json=body).status_code
        == 422
    )


def test_create_update_order_and_audit(db_client, lesson_data):
    db, classroom, _, _, _, _, actors = lesson_data
    authenticate(db_client, lesson_data, "lecturer")
    created = []
    for title in ["  Bài mới  ", "Bài tiếp"]:
        response = db_client.post(
            f"/api/classes/{classroom.id}/lessons", headers=CSRF, json={"title": title}
        )
        assert response.status_code == 201
        created.append(response.json())
    assert [item["position"] for item in created] == [3, 4]
    assert created[0]["title"] == "Bài mới" and not created[0]["is_published"]
    response = db_client.patch(
        f"/api/lessons/{created[0]['id']}",
        headers=CSRF,
        json={"title": "  Đổi tên  ", "position": 0, "is_published": True},
    )
    assert response.status_code == 200
    assert response.json() == {
        **created[0],
        "title": "Đổi tên",
        "position": 0,
        "is_published": True,
    }
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_id == actors["lecturer"])
        .order_by(AuditEvent.created_at)
    ).all()
    assert [event.action for event in events] == ["lesson.create", "lesson.create", "lesson.update"]
    assert events[0].detail == {"title": "Bài mới", "position": 3, "is_published": False}
    assert events[-1].detail == {"title": "Đổi tên", "position": 0, "is_published": True}
    assert all(event.target_type == "lesson" for event in events)
    response = db_client.patch(
        f"/api/lessons/{created[0]['id']}", headers=CSRF, json={"is_published": False}
    )
    assert response.status_code == 200
    authenticate(db_client, lesson_data, "student")
    assert created[0]["id"] not in [
        item["id"] for item in db_client.get(f"/api/classes/{classroom.id}").json()["lessons"]
    ]


def test_first_and_explicit_position(db_client, lesson_data):
    db, classroom, *_ = lesson_data
    empty = Class(course_id=classroom.course_id, code="EMPTY", term="2026")
    db.add(empty)
    db.flush()
    db.add(ClassMember(class_id=empty.id, user_id=lesson_data[6]["lecturer"], role="lecturer"))
    db.commit()
    authenticate(db_client, lesson_data, "lecturer")
    for body, position in [
        ({"title": "Đầu"}, 0),
        ({"title": "Chỉ định", "position": 8}, 8),
        ({"title": "Tiếp"}, 9),
    ]:
        response = db_client.post(f"/api/classes/{empty.id}/lessons", headers=CSRF, json=body)
        assert response.status_code == 201 and response.json()["position"] == position


@pytest.mark.parametrize("schema", [LessonCreate, LessonUpdate])
@pytest.mark.parametrize("title", ["", "   ", "x" * 201, None])
def test_title_schema_without_db(schema, title):
    with pytest.raises(ValidationError):
        schema(title=title)


def test_patch_schema_without_db():
    assert LessonCreate(title="  Bài học  ").title == "Bài học"
    assert LessonUpdate().model_fields_set == set()
    for field in ["title", "position", "is_published"]:
        with pytest.raises(ValidationError):
            LessonUpdate(**{field: None})
