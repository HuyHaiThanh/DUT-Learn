import sys
from collections import Counter
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pymupdf
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app import demo_seed
from app.assignments.models import Assignment, GradeRevision, Submission, SubmissionVersion
from app.auth.models import AuditEvent, User
from app.auth.security import verify_password
from app.config import get_settings
from app.courses.models import Class, ClassMember, Course, Lesson
from app.idempotency import IdempotencyKey
from app.ingest.worker import IngestWorker
from app.materials.models import Chunk, Material, MaterialVersion
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.progress.models import LearningEvent
from app.rag.embedder import FakeEmbedder
from app.tutor.models import ChatMessage, Citation

CSRF = {"X-DUT-CSRF": "1"}
DEMO_PASSWORD = uuid4().hex


@pytest.fixture(autouse=True)
def no_background_worker(monkeypatch):
    monkeypatch.setenv("DUT_INGEST_WORKER", "0")


@pytest.fixture
def demo_password(monkeypatch):
    password = DEMO_PASSWORD
    monkeypatch.setenv("DUT_DEMO_PASSWORD", password)
    monkeypatch.setenv("DUT_INGEST_WORKER", "0")
    return password


def counts(db):
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (
            User,
            Course,
            Class,
            ClassMember,
            Lesson,
            Assignment,
            Submission,
            SubmissionVersion,
            GradeRevision,
            PracticeQuestion,
            PracticeAttempt,
            LearningEvent,
            Material,
            MaterialVersion,
            Chunk,
            ChatMessage,
            Citation,
            IdempotencyKey,
            AuditEvent,
        )
    }


def login(client, account, password):
    client.cookies.clear()
    response = client.post(
        "/api/auth/login",
        headers=CSRF,
        json={
            "email": f"{account}@demo.dutlearn.local",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text


def test_demo_repeatable_states_and_permissions(test_engine, db_client, demo_password, capsys):
    with Session(test_engine) as db:
        initial = counts(db)
        class_id = demo_seed.seed(db)
        before = counts(db)
        assert before["chat_messages"] == initial["chat_messages"]
        assert before["citations"] == initial["citations"]
        epoch = db.get(Class, class_id).content_version
        assert demo_seed.seed(db) == class_id
        assert counts(db) == before
        assert db.get(Class, class_id).content_version == epoch
        output = capsys.readouterr().out
        assert demo_password not in output
        assert "Dữ liệu minh họa" in output
        assert "không có --pdf" in output
        assert f"/lop/{class_id}" in output
        users = {
            user.email.split("@")[0]: user
            for user in db.scalars(
                select(User).where(
                    User.email.in_(
                        [f"{account}@demo.dutlearn.local" for account, _, _ in demo_seed.ACCOUNTS]
                    )
                )
            )
        }
        assert len(users) == 6
        assert all(verify_password(demo_password, user.password_hash) for user in users.values())
        assert users["quantri"].system_role == "admin"
        assert all(user.system_role == "user" for key, user in users.items() if key != "quantri")
        lessons = list(
            db.scalars(select(Lesson).where(Lesson.class_id == class_id).order_by(Lesson.position))
        )
        assert [(item.title, item.is_published) for item in lessons] == [
            (title, index < 2) for index, title in enumerate(demo_seed.LESSONS)
        ]
        items = {
            item.title: item
            for item in db.scalars(
                select(Assignment).where(
                    Assignment.class_id == class_id,
                )
            )
        }
        assert [items[title].status for title in demo_seed.TITLES] == [
            "closed",
            "published",
            "draft",
        ]
        first, second, draft = [items[title] for title in demo_seed.TITLES]
        assert first.due_at.isoformat() == "2026-11-20T16:59:00+00:00"
        assert second.due_at.isoformat() == "2026-11-30T16:59:00+00:00"
        assert second.criteria == demo_seed.CRITERIA
        submissions = list(
            db.scalars(
                select(Submission).where(
                    Submission.assignment_id.in_([first.id, second.id, draft.id]),
                )
            )
        )
        assert len(submissions) == 4
        own_versions = list(
            db.scalars(
                select(SubmissionVersion).where(
                    SubmissionVersion.submission_id.in_([item.id for item in submissions]),
                )
            )
        )
        assert len(own_versions) == 5
        grades = list(
            db.scalars(
                select(GradeRevision).where(
                    GradeRevision.submission_version_id.in_([item.id for item in own_versions]),
                )
            )
        )
        assert Counter((g.grade, g.status) for g in grades) == Counter(
            [
                (Decimal("8"), "published"),
                (Decimal("7.5"), "published"),
                (Decimal("9"), "published"),
                (Decimal("7"), "draft"),
            ]
        )
        questions = list(
            db.scalars(
                select(PracticeQuestion).where(
                    PracticeQuestion.class_id == class_id,
                )
            )
        )
        assert len(questions) == 6
        assert all(q.origin == "lecturer" for q in questions)
        assert Counter((q.kind, q.status) for q in questions) == Counter(
            {
                ("mcq", "published"): 4,
                ("short", "published"): 1,
                ("mcq", "draft"): 1,
            }
        )
        attempts = list(
            db.scalars(
                select(PracticeAttempt).where(
                    PracticeAttempt.question_id.in_([q.id for q in questions]),
                )
            )
        )
        thao = [a for a in attempts if a.student_id == users["sv.thao"].id]
        duc = [a for a in attempts if a.student_id == users["sv.duc"].id]
        assert len(thao) == 4 and sum(a.is_correct for a in thao) == 3
        assert len(duc) == 2
        for account in ("sv.bao", "sv.anh"):
            assert not any(s.student_id == users[account].id for s in submissions)
            assert not any(a.student_id == users[account].id for a in attempts)
        events = list(db.scalars(select(LearningEvent).where(LearningEvent.class_id == class_id)))
        assert Counter(e.type for e in events) == {"submission_created": 5, "practice_attempted": 6}
        assert all(e.user_id != users["sv.anh"].id for e in events)

        login(db_client, "sv.duc", demo_password)
        response = db_client.get(f"/api/assignments/{second.id}/submissions/me")
        assert response.status_code == 200
        assert len(response.json()) == 1 and response.json()[0]["grade"] is None
        assert (
            db_client.patch(
                f"/api/assignments/{second.id}", headers=CSRF, json={"status": "closed"}
            ).status_code
            == 403
        )
        assert db_client.get(f"/api/assignments/{draft.id}").status_code == 404
        login(db_client, "sv.thao", demo_password)
        # The closed past assignment must not show its seeded submissions as late.
        past = db_client.get(f"/api/assignments/{first.id}/submissions/me").json()
        assert past and not any(v["is_late"] for v in past)
        response = db_client.get(f"/api/assignments/{second.id}/submissions/me")
        assert len(response.json()) == 2
        assert response.json()[0]["grade"] is None
        assert response.json()[1]["grade"]["grade"] == 9
        login(db_client, "quantri", demo_password)
        assert db_client.get(f"/api/assignments/{second.id}").status_code == 404
        assert db_client.get(f"/api/classes/{class_id}/practice").status_code == 404


def test_pdf_ingest_publish_repeat_and_revoke(
    test_engine,
    db_client,
    demo_password,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    monkeypatch.setattr(
        demo_seed,
        "IngestWorker",
        lambda: IngestWorker(
            sessionmaker(test_engine),
            embedder=FakeEmbedder(),
        ),
    )
    pdf = tmp_path / "demo.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Recursion uses a base case. int *p declares a pointer to int.")
        document.save(pdf)
    with Session(test_engine) as db:
        class_id = demo_seed.seed(db, pdf)
        material = db.scalar(select(Material).where(Material.class_id == class_id))
        version = db.get(MaterialVersion, material.active_version_id)
        assert material.title == "Giáo trình Lập trình căn bản"
        assert material.visibility == "students"
        assert material.source_note == "VOER — Giáo trình Lập trình căn bản"
        assert material.license_note == "CC BY 3.0"
        assert version.status == "published"
        assert db.scalar(select(Chunk.id).where(Chunk.version_id == version.id).limit(1))
        before = counts(db)
        epoch = db.get(Class, class_id).content_version
        # Published material skips even opening the supplied path.
        demo_seed.seed(db, tmp_path / "missing.pdf")
        assert counts(db) == before
        assert db.get(Class, class_id).content_version == epoch
        login(db_client, "sv.anh", demo_password)
        assert db_client.get(f"/api/material-versions/{version.id}/file").status_code == 200
        login(db_client, "quantri", demo_password)
        assert db_client.get(f"/api/material-versions/{version.id}/file").status_code == 404
        login(db_client, "gv.chau", demo_password)
        assert (
            db_client.post(f"/api/material-versions/{version.id}/revoke", headers=CSRF).status_code
            == 200
        )
        login(db_client, "sv.anh", demo_password)
        assert db_client.get(f"/api/material-versions/{version.id}/file").status_code == 404


@pytest.mark.parametrize("password", [None, "short", "123456789"])
def test_invalid_password_exits_before_db(monkeypatch, capsys, password):
    if password is None:
        monkeypatch.delenv("DUT_DEMO_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("DUT_DEMO_PASSWORD", password)
    factory = Mock(side_effect=AssertionError("Database must not be opened"))
    monkeypatch.setattr(demo_seed, "SessionLocal", factory)
    monkeypatch.setattr(sys, "argv", ["app.demo_seed"])
    with pytest.raises(SystemExit) as error:
        demo_seed.main()
    assert error.value.code == 1
    factory.assert_not_called()
    assert "DUT_DEMO_PASSWORD bắt buộc có và dài ít nhất 10 ký tự." in capsys.readouterr().err
    db = Mock()
    with pytest.raises(ValueError):
        demo_seed.seed(db)
    assert not db.mock_calls


@pytest.mark.parametrize("password", [None, "short"])
def test_invalid_password_leaves_database_unchanged(test_engine, monkeypatch, password):
    if password is None:
        monkeypatch.delenv("DUT_DEMO_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("DUT_DEMO_PASSWORD", password)
    with Session(test_engine) as db:
        before = counts(db)
        with pytest.raises(ValueError):
            demo_seed.seed(db)
        assert counts(db) == before
