from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import SessionToken, User
from app.auth.security import token_hash
from app.courses.models import Class, ClassMember, Course, Lesson
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.practice.schemas import QuestionCreate, StudentQuestion
from app.progress.models import LearningEvent

CSRF = {"X-DUT-CSRF": "1"}
MCQ = {
    "kind": "mcq",
    "stem": "1 + 1?",
    "options": ["1", "2"],
    "answer_key": "1",
    "explanation": "Một cộng một bằng hai.",
}


@pytest.fixture
def practice_data(test_engine):
    with Session(test_engine) as db:
        course = Course(code=uuid4().hex, name="Practice")
        db.add(course)
        db.flush()
        classroom = Class(course_id=course.id, code="A", term="2026.1")
        other = Class(course_id=course.id, code="B", term="2026.1")
        db.add_all([classroom, other])
        db.flush()
        tokens, actors = {}, {}
        for name, role, target in [
            ("lecturer", "lecturer", classroom),
            ("student", "student", classroom),
            ("peer", "student", classroom),
            ("other_student", "student", other),
            ("other_lecturer", "lecturer", other),
            ("admin", None, other),
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
            tokens[name], actors[name] = token, user.id
        foreign = Lesson(class_id=other.id, title="Other")
        db.add(foreign)
        db.commit()
        yield db, classroom, tokens, actors, foreign


def login(client, data, name):
    client.cookies.clear()
    if name:
        client.cookies.set("dut_session", data[2][name])


def create(client, data, body=None, publish=False):
    login(client, data, "lecturer")
    response = client.post(f"/api/classes/{data[1].id}/practice", headers=CSRF, json=body or MCQ)
    assert response.status_code == 201, response.text
    question = response.json()
    if publish:
        assert (
            client.post(f"/api/practice/{question['id']}/publish", headers=CSRF).status_code == 200
        )
    return question


def attempt(client, question, response="1", key=None):
    return client.post(
        f"/api/practice/{question['id']}/attempts",
        headers=CSRF,
        json={"response": response, "idempotency_key": key or str(uuid4())},
    )


def test_student_visibility_and_unpublished_attempts(db_client, practice_data):
    published = create(db_client, practice_data, publish=True)
    draft = create(db_client, practice_data)
    db, classroom, _, actors, _ = practice_data
    ai = PracticeQuestion(
        **MCQ, class_id=classroom.id, created_by=actors["lecturer"], origin="ai", status="approved"
    )
    retired = PracticeQuestion(
        **MCQ,
        class_id=classroom.id,
        created_by=actors["lecturer"],
        origin="lecturer",
        status="retired",
    )
    db.add_all([ai, retired])
    db.commit()
    login(db_client, practice_data, "student")
    result = db_client.get(f"/api/classes/{classroom.id}/practice?include_retired=true")
    assert result.status_code == 200
    assert [q["id"] for q in result.json()] == [published["id"]]
    assert '"answer_key"' not in result.text and '"explanation"' not in result.text
    assert result.json()[0]["my_attempts"] == 0
    for question_id in [draft["id"], str(ai.id), str(retired.id)]:
        assert attempt(db_client, {"id": question_id}).status_code == 404


def test_ai_approval_and_transition_rules(db_client, practice_data):
    lecturer = create(db_client, practice_data)
    assert (
        db_client.post(f"/api/practice/{lecturer['id']}/approve", headers=CSRF).status_code == 409
    )
    db, classroom, _, actors, _ = practice_data
    ai = PracticeQuestion(
        **MCQ, class_id=classroom.id, created_by=actors["lecturer"], origin="ai", status="draft"
    )
    db.add(ai)
    db.commit()
    path = f"/api/practice/{ai.id}"
    assert (
        db_client.post(path + "/publish", headers=CSRF).json()["error"]["code"]
        == "invalid_transition"
    )
    assert db_client.post(path + "/approve", headers=CSRF).json()["status"] == "approved"
    db.refresh(ai)
    assert ai.approved_by == actors["lecturer"] and ai.approved_at is not None
    assert db_client.patch(path, headers=CSRF, json={"stem": "New"}).json()["status"] == "draft"
    assert db_client.post(path + "/publish", headers=CSRF).status_code == 409
    assert db_client.post(path + "/approve", headers=CSRF).status_code == 200
    assert db_client.post(path + "/publish", headers=CSRF).json()["status"] == "published"
    assert db_client.post(path + "/publish", headers=CSRF).status_code == 409
    assert db_client.post(path + "/retire", headers=CSRF).json()["status"] == "retired"
    assert db_client.patch(path, headers=CSRF, json={"stem": "No"}).status_code == 409
    assert db_client.post(path + "/retire", headers=CSRF).status_code == 409


def test_grading_idempotency_snapshot_and_events(db_client, practice_data):
    question = create(db_client, practice_data, publish=True)
    login(db_client, practice_data, "student")
    key = str(uuid4())
    correct = attempt(db_client, question, key=key)
    assert correct.status_code == 200
    assert correct.json()["is_correct"] is True
    assert correct.json()["answer_key"] == "1"
    assert attempt(db_client, question, key=key).json() == correct.json()
    conflict = attempt(db_client, question, response="0", key=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert attempt(db_client, question, response="0").json()["is_correct"] is False
    for invalid in ["2", "-1", "01", "x", " 1", ""]:
        assert attempt(db_client, question, response=invalid).status_code == 422
    db, classroom, _, actors, _ = practice_data
    listed = db_client.get(f"/api/classes/{classroom.id}/practice").json()[0]
    assert listed["my_attempts"] == 2 and listed["my_last_correct"] is False
    assert (
        db.scalar(
            select(func.count())
            .select_from(PracticeAttempt)
            .where(PracticeAttempt.question_id == question["id"])
        )
        == 2
    )
    events = db.scalars(
        select(LearningEvent).where(
            LearningEvent.class_id == classroom.id, LearningEvent.type == "practice_attempted"
        )
    ).all()
    assert len(events) == 2
    assert all(
        e.ref_type == "practice_question" and str(e.ref_id) == question["id"] for e in events
    )
    login(db_client, practice_data, "lecturer")
    updated = db_client.patch(
        f"/api/practice/{question['id']}", headers=CSRF, json={"stem": "Changed", "answer_key": "0"}
    ).json()
    assert updated["id"] != question["id"] and updated["supersedes_id"] == question["id"]
    assert updated["status"] == "published" and updated["origin"] == "lecturer"
    assert len(db_client.get(f"/api/classes/{classroom.id}/practice").json()) == 1
    assert (
        len(db_client.get(f"/api/classes/{classroom.id}/practice?include_retired=true").json()) == 2
    )
    login(db_client, practice_data, "student")
    history = db_client.get(f"/api/practice/{question['id']}/attempts/me").json()
    assert len(history) == 2
    assert history[0]["question_snapshot"] == {k: MCQ[k] for k in MCQ}
    assert history[0]["answer_key"] == "1" and history[0]["explanation"] == MCQ["explanation"]
    assert attempt(db_client, question).status_code == 404
    login(db_client, practice_data, "peer")
    assert db_client.get(f"/api/practice/{question['id']}/attempts/me").json() == []


def test_short_response(db_client, practice_data):
    question = create(
        db_client,
        practice_data,
        {
            "kind": "short",
            "stem": "Explain",
            "answer_key": "Sample",
            "explanation": "Reason",
        },
        publish=True,
    )
    login(db_client, practice_data, "student")
    result = attempt(db_client, question, response="My answer").json()
    assert result["is_correct"] is None and result["answer_key"] == "Sample"
    assert result["explanation"] == "Reason"


@pytest.mark.parametrize("action", ["retire", "supersede"])
def test_retry_retired_question(db_client, practice_data, action):
    question = create(db_client, practice_data, publish=True)
    login(db_client, practice_data, "student")
    key = str(uuid4())
    first = attempt(db_client, question, key=key)
    assert first.status_code == 200
    login(db_client, practice_data, "lecturer")
    path = f"/api/practice/{question['id']}"
    if action == "retire":
        assert db_client.post(path + "/retire", headers=CSRF).status_code == 200
    else:
        assert db_client.patch(path, headers=CSRF, json={"stem": "New"}).status_code == 200
    login(db_client, practice_data, "student")
    retried = attempt(db_client, question, key=key)
    assert retried.status_code == 200
    assert retried.json() == first.json()
    assert len(db_client.get(path + "/attempts/me").json()) == 1
    assert attempt(db_client, question).status_code == 404
    conflict = attempt(db_client, question, response="0", key=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    for actor, status in [("other_student", 404), ("lecturer", 403)]:
        login(db_client, practice_data, actor)
        assert attempt(db_client, question, key=key).status_code == status
    practice_data[1].status = "closed"
    practice_data[0].commit()
    login(db_client, practice_data, "student")
    assert attempt(db_client, question, key=key).status_code == 404


@pytest.mark.parametrize(
    "actor,read,write",
    [
        ("student", 200, 403),
        ("other_student", 404, 404),
        ("other_lecturer", 404, 404),
        ("admin", 404, 404),
        (None, 401, 401),
    ],
)
def test_permissions(db_client, practice_data, actor, read, write):
    question = create(db_client, practice_data, publish=True)
    login(db_client, practice_data, actor)
    root = f"/api/classes/{practice_data[1].id}/practice"
    assert db_client.get(root).status_code == read
    assert db_client.post(root, headers=CSRF, json=MCQ).status_code == write
    path = f"/api/practice/{question['id']}"
    assert db_client.patch(path, headers=CSRF, json={"stem": "No"}).status_code == write
    for action in ["approve", "publish", "retire"]:
        assert db_client.post(path + "/" + action, headers=CSRF).status_code == write
    assert attempt(db_client, question).status_code == (200 if actor == "student" else read)
    assert db_client.get(path + "/attempts/me").status_code == read


def test_foreign_lesson_closed_class_and_student_only(db_client, practice_data):
    question = create(db_client, practice_data, publish=True)
    db, classroom, _, _, foreign = practice_data
    root = f"/api/classes/{classroom.id}/practice"
    assert (
        db_client.post(root, headers=CSRF, json={**MCQ, "lesson_id": str(foreign.id)}).status_code
        == 404
    )
    assert (
        db_client.patch(
            f"/api/practice/{question['id']}", headers=CSRF, json={"lesson_id": str(foreign.id)}
        ).status_code
        == 404
    )
    assert attempt(db_client, question).status_code == 403
    assert db_client.get(f"/api/practice/{question['id']}/attempts/me").status_code == 403
    classroom.status = "closed"
    db.commit()
    login(db_client, practice_data, "student")
    assert db_client.get(root).status_code == 404
    assert attempt(db_client, question).status_code == 404
    assert db_client.get(f"/api/practice/{question['id']}/attempts/me").status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"options": ["a"]},
        {"options": list("abcdefg")},
        {"options": ["a", "a"]},
        {"options": ["a", " a "]},
        {"options": ["", "b"]},
        {"options": ["x" * 1001, "b"]},
        {"answer_key": "2"},
        {"answer_key": "01"},
        {"answer_key": "-1"},
        {"kind": "short"},
        {"stem": ""},
        {"stem": " "},
        {"explanation": "x" * 5001},
    ],
)
def test_validation(changes):
    with pytest.raises(ValidationError):
        QuestionCreate.model_validate({**MCQ, **changes})


def test_student_schema_has_no_solution_fields():
    assert not {"answer_key", "explanation"} & StudentQuestion.model_fields.keys()


def test_http_validation(db_client, practice_data):
    question = create(db_client, practice_data)
    root = f"/api/classes/{practice_data[1].id}/practice"
    for changes in [
        {"options": ["a"]},
        {"options": list("abcdefg")},
        {"options": ["a", "a"]},
        {"answer_key": "7"},
    ]:
        assert db_client.post(root, headers=CSRF, json={**MCQ, **changes}).status_code == 422
        assert (
            db_client.patch(
                f"/api/practice/{question['id']}", headers=CSRF, json=changes
            ).status_code
            == 422
        )
    assert (
        db_client.patch(
            f"/api/practice/{question['id']}", headers=CSRF, json={"stem": None}
        ).status_code
        == 422
    )
