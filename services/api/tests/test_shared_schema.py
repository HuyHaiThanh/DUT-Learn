from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.assignments.models import Assignment, GradeRevision, Submission, SubmissionVersion
from app.auth.models import User
from app.courses.models import Class, Course, Lesson
from app.db import Base
from app.errors import APIError
from app.idempotency import IdempotencyKey, find, payload_hash, remember, validate_key
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.progress.events import record_event
from app.progress.models import LearningEvent

SHARED_TABLES = {
    "assignments",
    "submissions",
    "submission_versions",
    "grade_revisions",
    "practice_questions",
    "practice_attempts",
    "idempotency_keys",
    "learning_events",
}


def test_shared_migration_roundtrip(test_engine):
    schema = "shared_migration_" + uuid4().hex
    with test_engine.begin() as connection:
        original = connection.scalar(text("SHOW search_path"))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert SHARED_TABLES <= set(inspect(connection).get_table_names(schema=schema))
        for name in SHARED_TABLES:
            inspector = inspect(connection)
            columns = {c["name"]: c for c in inspector.get_columns(name, schema=schema)}
            model = Base.metadata.tables[name]
            assert set(columns) == set(model.columns.keys())
            for column in model.columns:
                assert columns[column.name]["nullable"] == column.nullable
            assert {c["name"] for c in inspector.get_check_constraints(name, schema=schema)} == {
                c.name for c in model.constraints if c.__class__.__name__ == "CheckConstraint"
            }
            assert {
                tuple(i["column_names"]) for i in inspector.get_indexes(name, schema=schema)
            } >= {tuple(c.name for c in index.columns) for index in model.indexes}
            assert {
                tuple(c["column_names"])
                for c in inspector.get_unique_constraints(name, schema=schema)
            } == {
                tuple(c.name for c in constraint.columns)
                for constraint in model.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            }
            foreign_keys = inspector.get_foreign_keys(name, schema=schema)
            assert len(foreign_keys) == len(model.foreign_keys)
            assert all(
                fk["options"].get("ondelete", "NO ACTION") == "NO ACTION" for fk in foreign_keys
            )
        command.downgrade(config, "0005_reading_positions")
        assert SHARED_TABLES.isdisjoint(inspect(connection).get_table_names(schema=schema))
        assert "reading_positions" in inspect(connection).get_table_names(schema=schema)
        command.upgrade(config, "head")
        assert SHARED_TABLES <= set(inspect(connection).get_table_names(schema=schema))
        connection.execute(text(f"SET LOCAL search_path TO {original}"))
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def shared_db(test_engine):
    with test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            user = User(
                email=f"{uuid4().hex}@example.test", full_name="Test", password_hash="unused"
            )
            course = Course(code=uuid4().hex, name="Test")
            db.add_all([user, course])
            db.flush()
            classroom = Class(course_id=course.id, code="TEST", term="2026.1")
            db.add(classroom)
            db.flush()
            lesson = Lesson(class_id=classroom.id, title="Test")
            db.add(lesson)
            db.flush()
            assignment = Assignment(
                class_id=classroom.id,
                lesson_id=lesson.id,
                title="Test",
                instructions="Submit",
                criteria="Criteria",
                created_by=user.id,
            )
            db.add(assignment)
            db.flush()
            submission = Submission(assignment_id=assignment.id, student_id=user.id)
            db.add(submission)
            db.flush()
            version = SubmissionVersion(submission_id=submission.id, version_no=1, content="Answer")
            db.add(version)
            question = PracticeQuestion(
                class_id=classroom.id,
                lesson_id=lesson.id,
                kind="short",
                stem="Question",
                answer_key="Answer",
                explanation="Explanation",
                origin="lecturer",
                created_by=user.id,
            )
            db.add(question)
            db.flush()
            yield db, user, classroom, lesson, assignment, submission, version, question
        transaction.rollback()


@pytest.mark.parametrize(
    "case",
    [
        "assignment_status",
        "grade",
        "grade_status",
        "revision",
        "revision_duplicate",
        "submission_duplicate",
        "version",
        "version_duplicate",
        "question_kind",
        "question_origin",
        "question_status",
        "event_type",
        "key_duplicate",
    ],
)
def test_shared_constraints(shared_db, case):
    db, user, classroom, _, assignment, submission, version, question = shared_db
    with pytest.raises(IntegrityError), db.begin_nested():
        if case == "assignment_status":
            assignment.status = "unknown"
        elif case in {"grade", "grade_status", "revision", "revision_duplicate"}:
            data = dict(
                submission_version_id=version.id,
                revision_no=1,
                grade=5,
                comment="Feedback",
                criteria_snapshot="Criteria",
                created_by=user.id,
            )
            if case == "grade":
                data["grade"] = 11
            elif case == "grade_status":
                data["status"] = "unknown"
            elif case == "revision":
                data["revision_no"] = 0
            if case == "revision_duplicate":
                db.add(GradeRevision(**data))
                db.flush()
            db.add(GradeRevision(**data))
        elif case == "submission_duplicate":
            db.add(Submission(assignment_id=assignment.id, student_id=user.id))
        elif case in {"version", "version_duplicate"}:
            db.add(
                SubmissionVersion(
                    submission_id=submission.id,
                    version_no=0 if case == "version" else 1,
                    content="Other",
                )
            )
        elif case.startswith("question_"):
            setattr(question, case.removeprefix("question_"), "unknown")
        elif case == "event_type":
            db.add(LearningEvent(user_id=user.id, class_id=classroom.id, type="unknown"))
        elif case == "key_duplicate":
            for _ in range(2):
                remember(db, user.id, "submission", "same-key", {}, "submission", submission.id)
                db.flush()
        db.flush()


@pytest.mark.parametrize("entity", ["class", "lesson"])
def test_learning_data_prevents_parent_deletion(shared_db, entity):
    db, _, classroom, lesson, *_ = shared_db
    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(classroom if entity == "class" else lesson)
        db.flush()


def test_hash_is_canonical_and_excludes_key():
    assert payload_hash({"b": {"y": 2, "x": 1}, "a": 3, "idempotency_key": "one"}) == payload_hash(
        {"a": 3, "idempotency_key": "two", "b": {"x": 1, "y": 2}}
    )
    assert payload_hash({"a": 1}) != payload_hash({"a": "1"})
    assert len(payload_hash({})) == 64


@pytest.mark.parametrize("key", ["", "a" * 7, "a" * 101, None, 123])
def test_invalid_key(key):
    with pytest.raises(APIError) as error:
        validate_key(key)
    assert error.value.status_code == 422
    assert error.value.code == "validation_error"


@pytest.mark.parametrize("key", ["a" * 8, "a" * 100])
def test_valid_key(key):
    validate_key(key)


def test_idempotency_replay_conflict_and_scope(shared_db):
    db, user, _, _, _, submission, *_ = shared_db
    payload = {"content": "Answer", "idempotency_key": "client-key"}
    assert find(db, user.id, "submission", "client-key", payload) is None
    remember(db, user.id, "submission", "client-key", payload, "submission", submission.id)
    assert find(db, user.id, "submission", "client-key", payload) == ("submission", submission.id)
    assert db.scalar(select(func.count()).select_from(IdempotencyKey)) == 1
    assert find(db, user.id, "practice_attempt", "client-key", payload) is None
    assert find(db, uuid4(), "submission", "client-key", payload) is None
    with pytest.raises(APIError) as error:
        find(db, user.id, "submission", "client-key", {"content": "Changed"})
    assert error.value.status_code == 409
    assert error.value.code == "idempotency_conflict"


def test_helpers_do_not_commit():
    db = Mock(spec=Session)
    user_id, class_id, ref_id = uuid4(), uuid4(), uuid4()
    record_event(db, user_id, class_id, "submission_created", "submission", ref_id)
    event = db.add.call_args.args[0]
    assert isinstance(event, LearningEvent)
    assert (event.user_id, event.class_id, event.type, event.ref_type, event.ref_id) == (
        user_id,
        class_id,
        "submission_created",
        "submission",
        ref_id,
    )
    remember(db, user_id, "submission", "client-key", {}, "submission", ref_id)
    assert db.add.call_count == 2
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_event_and_key_rollback_with_created_record(shared_db):
    db, user, classroom, _, _, _, _, question = shared_db
    with db.begin_nested() as transaction:
        attempt = PracticeAttempt(
            question_id=question.id,
            student_id=user.id,
            question_snapshot={"stem": question.stem},
            response="Answer",
        )
        db.add(attempt)
        db.flush()
        attempt_id = attempt.id
        record_event(
            db, user.id, classroom.id, "practice_attempted", "practice_attempt", attempt.id
        )
        remember(
            db, user.id, "practice_attempt", "rollback-key", {}, "practice_attempt", attempt.id
        )
        db.flush()
        assert db.scalar(select(func.count()).select_from(LearningEvent)) == 1
        assert db.scalar(select(LearningEvent)).ref_id == attempt.id
        transaction.rollback()
    assert db.get(PracticeAttempt, attempt_id) is None
    assert db.scalar(select(func.count()).select_from(LearningEvent)) == 0
    assert find(db, user.id, "practice_attempt", "rollback-key", {}) is None
