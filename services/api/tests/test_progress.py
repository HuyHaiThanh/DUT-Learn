from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_tutor import tutor as tutor

from app.assignments.models import Assignment, GradeRevision, Submission, SubmissionVersion
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.progress.events import record_event
from app.progress.models import LearningEvent


def event(world, type, ref_id, class_id=None):
    return world.client.post(
        "/api/events",
        json={
            "class_id": str(class_id or world.classes[0].id),
            "type": type,
            "ref_id": str(ref_id),
        },
        headers={"X-DUT-CSRF": "1"},
    )


def progress(world, suffix="/me", class_id=None):
    return world.client.get(f"/api/classes/{class_id or world.classes[0].id}/progress{suffix}")


@pytest.fixture
def results(tutor):
    db = tutor.db
    assignment = Assignment(
        class_id=tutor.classes[0].id,
        title="Synthetic assignment",
        instructions="Synthetic",
        criteria="Synthetic",
        status="published",
        created_by=tutor.users[1].id,
    )
    question = PracticeQuestion(
        class_id=tutor.classes[0].id,
        kind="mcq",
        stem="Synthetic",
        options=["A", "B"],
        answer_key="0",
        explanation="Synthetic",
        origin="lecturer",
        status="published",
        created_by=tutor.users[1].id,
    )
    db.add_all([assignment, question])
    db.flush()
    submission = Submission(assignment_id=assignment.id, student_id=tutor.users[0].id)
    db.add(submission)
    db.flush()
    version = SubmissionVersion(submission_id=submission.id, version_no=1, content="Synthetic")
    db.add(version)
    db.flush()
    grade = GradeRevision(
        submission_version_id=version.id,
        revision_no=1,
        grade=Decimal("8.50"),
        comment="Synthetic",
        criteria_snapshot="Synthetic",
        created_by=tutor.users[1].id,
        status="draft",
    )
    db.add(grade)
    now = datetime.now(UTC)
    for index, correct in enumerate([False, True]):
        db.add(
            PracticeAttempt(
                question_id=question.id,
                student_id=tutor.users[0].id,
                question_snapshot={"kind": "mcq"},
                response="0",
                is_correct=correct,
                submitted_at=now + timedelta(seconds=index),
            )
        )
    db.commit()
    return assignment, submission, version, grade, question


def test_real_counts_repeated_material_revoke_draft_and_last_attempt(tutor, results):
    for _ in range(3):
        record_event(
            tutor.db,
            tutor.users[0].id,
            tutor.classes[0].id,
            "material_opened",
            "material",
            tutor.materials[0].id,
        )
    record_event(
        tutor.db,
        tutor.users[0].id,
        tutor.classes[0].id,
        "material_opened",
        "material",
        tutor.materials[1].id,
    )
    tutor.versions[1].status = "revoked"
    tutor.materials[1].active_version_id = None
    tutor.db.commit()
    data = progress(tutor).json()
    assert data["activity"]["materials_opened"] == 1
    assert data["activity"]["materials_available"] == 1
    assert data["results"] == {
        "assignments_submitted": 1,
        "assignments_available": 1,
        "grades": [],
        "practice_attempted": 1,
        "practice_available": 1,
        "practice_mcq_correct_last": 1,
        "practice_mcq_attempted": 1,
    }
    results[4].status = "retired"
    tutor.db.commit()
    assert progress(tutor).json()["results"]["practice_attempted"] == 0


def test_published_grade_latest_revision_of_latest_graded_submission(tutor, results):
    assignment, submission, version, grade, _ = results
    grade.status = "published"
    grade.published_at = datetime.now(UTC)
    tutor.db.add(
        GradeRevision(
            submission_version_id=version.id,
            revision_no=2,
            grade=Decimal("2"),
            comment="Draft",
            criteria_snapshot="Synthetic",
            created_by=tutor.users[1].id,
            status="draft",
        )
    )
    tutor.db.add(SubmissionVersion(submission_id=submission.id, version_no=2, content="Ungraded"))
    tutor.db.commit()
    grades = progress(tutor).json()["results"]["grades"]
    assert len(grades) == 1 and grades[0]["grade"] == 8.5
    assert grades[0]["assignment_id"] == str(assignment.id)
    assert event(tutor, "feedback_viewed", grade.id).status_code == 204


def test_events_validate_sources_and_deduplicate(tutor, results):
    material = tutor.materials[0]
    assert event(tutor, "material_opened", material.id).status_code == 204
    assert event(tutor, "material_opened", material.id).status_code == 204
    rows = list(
        tutor.db.scalars(
            select(LearningEvent).where(
                LearningEvent.user_id == tutor.users[0].id,
                LearningEvent.ref_id == material.id,
            )
        )
    )
    assert len(rows) == 1
    rows[0].occurred_at = datetime.now(UTC) - timedelta(minutes=11)
    tutor.db.commit()
    assert event(tutor, "material_opened", material.id).status_code == 204
    assert (
        tutor.db.scalar(
            select(func.count())
            .select_from(LearningEvent)
            .where(
                LearningEvent.user_id == tutor.users[0].id,
                LearningEvent.ref_id == material.id,
            )
        )
        == 2
    )
    material.visibility = "lecturers"
    tutor.db.commit()
    assert event(tutor, "material_opened", material.id).status_code == 404
    material.visibility = "students"
    tutor.versions[0].status = "revoked"
    tutor.db.commit()
    assert event(tutor, "material_opened", material.id).status_code == 404
    assert event(tutor, "feedback_viewed", results[3].id).status_code == 404
    assert event(tutor, "question_asked", material.id).status_code == 422
    assert event(tutor, "unknown", material.id).status_code == 422
    assert event(tutor, "material_opened", uuid4()).status_code == 404
    tutor.actor[0] = 2
    assert event(tutor, "material_opened", material.id, tutor.classes[1].id).status_code == 404


def test_citation_owner_and_feedback_owner(tutor, results):
    response = tutor.post().json()
    citation = response["citations"][0]["id"]
    assert event(tutor, "citation_opened", citation).status_code == 204
    tutor.actor[0] = 5
    assert event(tutor, "citation_opened", citation).status_code == 404
    grade = results[3]
    grade.status = "published"
    grade.published_at = datetime.now(UTC)
    tutor.db.commit()
    assert event(tutor, "feedback_viewed", grade.id).status_code == 404
    tutor.actor[0] = 2
    assert event(tutor, "citation_opened", citation, tutor.classes[1].id).status_code == 404
    assert event(tutor, "feedback_viewed", grade.id, tutor.classes[1].id).status_code == 404


@pytest.mark.parametrize(
    "actor,suffix,status",
    [(0, "", 403), (1, "/me", 403), (2, "/me", 404), (4, "/me", 404), (4, "", 404)],
)
def test_progress_permissions(tutor, actor, suffix, status):
    tutor.actor[0] = actor
    assert progress(tutor, suffix).status_code == status


def test_lecturer_sorted_students_without_question_content(tutor):
    tutor.users[0].full_name = "B Synthetic"
    tutor.users[5].full_name = "A Synthetic"
    tutor.db.commit()
    tutor.post()
    tutor.actor[0] = 1
    response = progress(tutor, "")
    assert response.status_code == 200
    rows = response.json()
    assert [s["full_name"] for s in rows] == ["A Synthetic", "B Synthetic"]
    assert rows[1]["activity"]["questions_asked"] == 1
    assert set(rows[1]) == {"user_id", "full_name", "activity", "results", "last_activity_at"}
    assert "needle" not in response.text and "Synthetic answer" not in response.text


def test_question_event_counts_answers_and_evidence_gate_refusals(tutor):
    response = tutor.post()
    assert response.status_code == 200
    rows = list(
        tutor.db.scalars(
            select(LearningEvent).where(
                LearningEvent.user_id == tutor.users[0].id,
                LearningEvent.type == "question_asked",
            )
        )
    )
    assert len(rows) == 1
    assert rows[0].ref_type == "chat_message"
    assert rows[0].ref_id == UUID(response.json()["message_id"])
    tutor.settings.min_score_dense = 1.1
    tutor.fake.generate = lambda *args, **kwargs: pytest.fail("LLM must not be called")
    assert tutor.post().json()["status"] == "insufficient_evidence"
    # Asking is learning activity even when the materials lack evidence.
    assert progress(tutor).json()["activity"]["questions_asked"] == 2
