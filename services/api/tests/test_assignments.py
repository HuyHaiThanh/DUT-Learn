from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assignments import service
from app.assignments.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    GradeCreate,
    SubmissionCreate,
)
from app.auth.models import SessionToken, User
from app.auth.security import token_hash
from app.courses.models import Class, ClassMember, Course, Lesson
from app.progress.models import LearningEvent

CSRF = {"X-DUT-CSRF": "1"}


@pytest.fixture
def data(test_engine):
    with Session(test_engine) as db:
        course = Course(code=uuid4().hex, name="Assignments")
        db.add(course)
        db.flush()
        classroom = Class(course_id=course.id, code="T19", term="2026.1")
        other = Class(course_id=course.id, code="Other", term="2026.1")
        db.add_all([classroom, other])
        db.flush()
        tokens = {}
        users = {}
        for name, role, target in [
            ("lecturer", "lecturer", classroom),
            ("student", "student", classroom),
            ("student_b", "student", classroom),
            ("unsubmitted", "student", classroom),
            ("other_student", "student", other),
            ("other_lecturer", "lecturer", other),
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
            users[name] = user.id
        foreign = Lesson(class_id=other.id, title="Other lesson")
        db.add(foreign)
        db.commit()
        yield {"db": db, "class": classroom, "tokens": tokens, "users": users, "foreign": foreign}


def auth(client, data, actor):
    client.cookies.clear()
    client.cookies.set("dut_session", data["tokens"][actor])


def write(client, method, path, body=None, expected=200):
    response = client.request(method, f"/api{path}", headers=CSRF, json=body)
    assert response.status_code == expected, response.text
    return response.json() if expected != 204 else None


def create(client, data, published=True):
    auth(client, data, "lecturer")
    item = write(
        client,
        "POST",
        f"/classes/{data['class'].id}/assignments",
        {
            "title": "Bài tập",
            "instructions": "Implement",
            "criteria": "Correctness",
            "due_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
        201,
    )
    if published:
        write(client, "PATCH", f"/assignments/{item['id']}", {"status": "published"})
    return item["id"]


def submit(client, id, content="answer", key=None, expected=200):
    return write(
        client,
        "POST",
        f"/assignments/{id}/submissions",
        {"content": content, "idempotency_key": key or str(uuid4())},
        expected,
    )


def seeded(client, data):
    id = create(client, data)
    auth(client, data, "student")
    version = submit(client, id)
    auth(client, data, "lecturer")
    grade = write(
        client,
        "POST",
        f"/submission-versions/{version['version_id']}/grades",
        {"grade": 7.25, "comment": "Draft feedback"},
    )
    return id, version["version_id"], grade["revision_id"]


def endpoints(data, id, version, revision):
    return [
        ("GET", f"/classes/{data['class'].id}/assignments", None),
        ("POST", f"/classes/{data['class'].id}/assignments", {"title": "New"}),
        ("GET", f"/assignments/{id}", None),
        ("PATCH", f"/assignments/{id}", {"title": "Changed"}),
        ("DELETE", f"/assignments/{id}", None),
        (
            "POST",
            f"/assignments/{id}/submissions",
            {"content": "x", "idempotency_key": str(uuid4())},
        ),
        ("GET", f"/assignments/{id}/submissions/me", None),
        ("GET", f"/assignments/{id}/submissions", None),
        ("GET", f"/submission-versions/{version}", None),
        ("POST", f"/submission-versions/{version}/grades", {"grade": 5}),
        ("POST", f"/grade-revisions/{revision}/publish", None),
    ]


def test_full_flow(db_client, data):
    id = create(db_client, data)
    auth(db_client, data, "student")
    first = submit(db_client, id, "First")
    second = submit(db_client, id, "Second")
    assert [first["version_no"], second["version_no"]] == [1, 2]
    assert second["is_late"] is True
    auth(db_client, data, "lecturer")
    path = f"/submission-versions/{second['version_id']}/grades"
    draft = write(db_client, "POST", path, {"grade": 7.25, "comment": "Good"})
    updated = write(db_client, "POST", path, {"grade": 8, "comment": "Better"})
    assert updated["revision_id"] == draft["revision_id"]
    auth(db_client, data, "student")
    me = f"/api/assignments/{id}/submissions/me"
    assert [v["grade"] for v in db_client.get(me).json()] == [None, None]
    auth(db_client, data, "lecturer")
    published = write(db_client, "POST", f"/grade-revisions/{draft['revision_id']}/publish")
    assert published["published_at"] and published["published_by"]
    write(db_client, "POST", f"/grade-revisions/{draft['revision_id']}/publish", expected=409)
    write(db_client, "PATCH", f"/assignments/{id}", {"criteria": "New criteria"})
    revision = write(db_client, "POST", path, {"grade": 9, "comment": "Revised"})
    assert revision["revision_no"] == 2 and revision["criteria_snapshot"] == "New criteria"
    auth(db_client, data, "student")
    own = db_client.get(me).json()
    assert own[0]["grade"] is None
    assert own[1]["grade"]["grade"] == 8 and own[1]["grade"]["comment"] == "Better"
    # The published revision (not the newer draft) is what feedback_viewed refers to.
    assert own[1]["grade"]["revision_id"] == draft["revision_id"]
    assert "criteria_snapshot" not in own[1]["grade"]
    auth(db_client, data, "lecturer")
    write(db_client, "POST", f"/grade-revisions/{revision['revision_id']}/publish")
    roster = db_client.get(f"/api/assignments/{id}/submissions").json()
    assert [s["student"]["full_name"] for s in roster] == ["student", "student_b", "unsubmitted"]
    assert roster[-1]["versions"] == []
    history = db_client.get(f"/api/submission-versions/{second['version_id']}").json()["revisions"]
    assert history[0]["grade"] == 8 and history[0]["criteria_snapshot"] == "Correctness"
    auth(db_client, data, "student")
    assert db_client.get(me).json()[1]["grade"]["grade"] == 9
    summary = db_client.get(f"/api/classes/{data['class'].id}/assignments").json()[0]
    assert summary["my_versions"] == 2 and summary["my_grade_published"] is True
    assert summary["my_is_late"] is True and summary["my_last_submitted_at"]
    db = data["db"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(LearningEvent)
            .where(
                LearningEvent.user_id == data["users"]["student"],
                LearningEvent.type == "submission_created",
            )
        )
        == 2
    )


def test_idempotency(db_client, data):
    id = create(db_client, data)
    auth(db_client, data, "student")
    key = str(uuid4())
    first = submit(db_client, id, key=key)
    assert submit(db_client, id, key=key)["version_id"] == first["version_id"]
    conflict = submit(db_client, id, "different", key, 409)
    assert conflict["error"]["code"] == "idempotency_conflict"
    assert len(db_client.get(f"/api/assignments/{id}/submissions/me").json()) == 1
    other = create(db_client, data)
    auth(db_client, data, "student")
    assert (
        submit(db_client, other, key=key, expected=409)["error"]["code"] == "idempotency_conflict"
    )


def test_draft_refreshes_criteria_snapshot(db_client, data):
    id, version, revision = seeded(db_client, data)
    write(db_client, "PATCH", f"/assignments/{id}", {"criteria": "Updated criteria"})
    saved = write(
        db_client, "POST", f"/submission-versions/{version}/grades", {"grade": 8.5}
    )
    assert saved["revision_id"] == revision
    published = write(db_client, "POST", f"/grade-revisions/{revision}/publish")
    assert published["criteria_snapshot"] == "Updated criteria"
    write(db_client, "PATCH", f"/assignments/{id}", {"criteria": "Later criteria"})
    write(db_client, "POST", f"/submission-versions/{version}/grades", {"grade": 9})
    history = db_client.get(f"/api/submission-versions/{version}").json()["revisions"]
    assert history[0]["criteria_snapshot"] == "Updated criteria"
    assert history[1]["criteria_snapshot"] == "Later criteria"


@pytest.mark.parametrize("actor", ["other_student", "other_lecturer", "admin"])
def test_nonmember_every_endpoint(db_client, data, actor):
    id, version, revision = seeded(db_client, data)
    auth(db_client, data, actor)
    for method, path, body in endpoints(data, id, version, revision):
        write(db_client, method, path, body, 404)


def test_wrong_role(db_client, data):
    id, version, revision = seeded(db_client, data)
    auth(db_client, data, "student")
    for index in [1, 3, 4, 7, 8, 9, 10]:
        method, path, body = endpoints(data, id, version, revision)[index]
        write(db_client, method, path, body, 403)
    auth(db_client, data, "lecturer")
    submit(db_client, id, expected=403)
    assert db_client.get(f"/api/assignments/{id}/submissions/me").status_code == 403


def test_draft_hidden(db_client, data):
    id = create(db_client, data, False)
    auth(db_client, data, "student")
    assert db_client.get(f"/api/assignments/{id}").status_code == 404
    submit(db_client, id, expected=404)
    assert db_client.get(f"/api/assignments/{id}/submissions/me").status_code == 404
    assert db_client.get(f"/api/classes/{data['class'].id}/assignments").json() == []


def test_student_cannot_read_another_student(db_client, data):
    id, version, _ = seeded(db_client, data)
    auth(db_client, data, "student_b")
    assert db_client.get(f"/api/assignments/{id}/submissions/me").json() == []
    assert db_client.get(f"/api/submission-versions/{version}").status_code == 403
    assert db_client.get(f"/api/assignments/{id}/submissions").status_code == 403


def test_closed_class_every_endpoint(db_client, data):
    id, version, revision = seeded(db_client, data)
    data["class"].status = "closed"
    data["db"].commit()
    auth(db_client, data, "student")
    for method, path, body in endpoints(data, id, version, revision):
        write(db_client, method, path, body, 404)


def test_foreign_lesson(db_client, data):
    id = create(db_client, data)
    write(
        db_client,
        "POST",
        f"/classes/{data['class'].id}/assignments",
        {"title": "Invalid", "lesson_id": str(data["foreign"].id)},
        404,
    )
    write(db_client, "PATCH", f"/assignments/{id}", {"lesson_id": str(data["foreign"].id)}, 404)


def test_close_reopen_and_transitions(db_client, data):
    id = create(db_client, data)
    write(db_client, "PATCH", f"/assignments/{id}", {"status": "draft"}, 409)
    write(db_client, "DELETE", f"/assignments/{id}", expected=409)
    write(db_client, "PATCH", f"/assignments/{id}", {"status": "closed"})
    auth(db_client, data, "student")
    assert db_client.get(f"/api/assignments/{id}").status_code == 200
    assert submit(db_client, id, expected=409)["error"]["code"] == "assignment_closed"
    auth(db_client, data, "lecturer")
    write(db_client, "PATCH", f"/assignments/{id}", {"status": "published"})
    auth(db_client, data, "student")
    assert submit(db_client, id)["is_late"] is True
    auth(db_client, data, "lecturer")
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    write(db_client, "PATCH", f"/assignments/{id}", {"due_at": future})
    auth(db_client, data, "student")
    assert submit(db_client, id)["is_late"] is False
    draft = create(db_client, data, False)
    write(db_client, "PATCH", f"/assignments/{draft}", {"status": "closed"}, 409)
    write(db_client, "DELETE", f"/assignments/{draft}", expected=204)


@pytest.mark.parametrize(
    "payload",
    [
        {"grade": -1},
        {"grade": 11},
        {"grade": "1.234"},
        {"grade": "NaN"},
        {},
        {"comment": " "},
        {"comment": "x" * 5001},
    ],
)
def test_grade_validation(payload):
    with pytest.raises(ValidationError):
        GradeCreate(**payload)


def test_limits_and_feedback_only():
    assert GradeCreate(grade=Decimal("0")).grade == 0
    assert GradeCreate(comment="Feedback").grade is None
    assert AssignmentUpdate().model_dump(exclude_unset=True) == {}
    for model, payload in [
        (AssignmentCreate, {"title": ""}),
        (AssignmentCreate, {"title": "x" * 201}),
        (AssignmentCreate, {"title": "x", "instructions": "x" * 20001}),
        (AssignmentCreate, {"title": "x", "criteria": "x" * 5001}),
        (AssignmentUpdate, {"status": None}),
        (SubmissionCreate, {"content": "", "idempotency_key": "12345678"}),
        (SubmissionCreate, {"content": "x", "idempotency_key": "short"}),
        (SubmissionCreate, {"content": "x" * 20001, "idempotency_key": "12345678"}),
    ]:
        with pytest.raises(ValidationError):
            model(**payload)


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_submissions(db_client, data, test_engine, same_key):
    assignment_id = UUID(create(db_client, data))
    student_id = data["users"]["student"]
    key = str(uuid4())

    def send(index):
        with Session(test_engine) as db:
            user = db.get(User, student_id)
            item = service.assignment(db, user, assignment_id, "student")
            return service.submit(
                db,
                user,
                item,
                SubmissionCreate(
                    content="Concurrent", idempotency_key=key if same_key else str(uuid4())
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    if same_key:
        assert results[0]["version_id"] == results[1]["version_id"]
    else:
        assert sorted(r["version_no"] for r in results) == [1, 2]
    auth(db_client, data, "student")
    assert len(db_client.get(f"/api/assignments/{assignment_id}/submissions/me").json()) == (
        1 if same_key else 2
    )
