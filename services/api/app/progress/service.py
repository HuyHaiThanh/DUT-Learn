from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assignments.models import Assignment, GradeRevision, Submission, SubmissionVersion
from app.auth.models import User
from app.deps import class_role, require_class_member
from app.materials.models import Material, MaterialVersion
from app.materials.policy import can_read_version
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.progress.events import record_event
from app.progress.models import LearningEvent
from app.progress.schemas import Activity, EventInput, Grade, ProgressResponse, Results
from app.tutor.models import ChatMessage, ChatSession, Citation


def receive_event(db: Session, user: User, data: EventInput) -> None:
    require_class_member(data.class_id, db, user)
    ref_type = "material"
    valid = False
    if data.type == "material_opened":
        material = db.get(Material, data.ref_id)
        version = (
            db.get(MaterialVersion, material.active_version_id)
            if material and material.active_version_id
            else None
        )
        valid = bool(
            material
            and material.class_id == data.class_id
            and version
            and can_read_version(db, user, version)
        )
    elif data.type == "citation_opened":
        ref_type = "citation"
        citation = db.get(Citation, data.ref_id)
        owner = (
            db.scalar(
                select(ChatSession)
                .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
                .where(ChatMessage.id == citation.message_id)
            )
            if citation
            else None
        )
        version = db.get(MaterialVersion, citation.version_id) if citation else None
        valid = bool(
            owner
            and owner.user_id == user.id
            and owner.class_id == data.class_id
            and version
            and can_read_version(db, user, version)
        )
    else:
        ref_type = "grade_revision"
        valid = (
            class_role(db, user, data.class_id) == "student"
            and db.scalar(
                select(GradeRevision.id)
                .join(
                    SubmissionVersion, SubmissionVersion.id == GradeRevision.submission_version_id
                )
                .join(Submission, Submission.id == SubmissionVersion.submission_id)
                .join(Assignment, Assignment.id == Submission.assignment_id)
                .where(
                    GradeRevision.id == data.ref_id,
                    GradeRevision.status == "published",
                    Submission.student_id == user.id,
                    Assignment.class_id == data.class_id,
                    Assignment.status.in_(["published", "closed"]),
                )
            )
            is not None
        )
    if not valid:
        raise HTTPException(404)
    # Serialize this user's event requests so concurrent retries also deduplicate.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    recent = db.scalar(
        select(LearningEvent.id)
        .where(
            LearningEvent.user_id == user.id,
            LearningEvent.type == data.type,
            LearningEvent.ref_id == data.ref_id,
            LearningEvent.occurred_at >= func.clock_timestamp() - timedelta(minutes=10),
        )
        .limit(1)
    )
    if recent is None:
        record_event(db, user.id, data.class_id, data.type, ref_type, data.ref_id)
    db.commit()


def student_progress(db: Session, class_id: UUID, user_id: UUID) -> ProgressResponse:
    material_ids = set(
        db.scalars(
            select(Material.id)
            .join(MaterialVersion, MaterialVersion.id == Material.active_version_id)
            .where(
                Material.class_id == class_id,
                Material.visibility == "students",
                MaterialVersion.status == "published",
            )
        )
    )
    events = list(
        db.scalars(
            select(LearningEvent).where(
                LearningEvent.class_id == class_id,
                LearningEvent.user_id == user_id,
            )
        )
    )
    assignments = list(
        db.scalars(
            select(Assignment)
            .where(
                Assignment.class_id == class_id,
                Assignment.status.in_(["published", "closed"]),
            )
            .order_by(Assignment.title, Assignment.id)
        )
    )
    grades = []
    submitted = 0
    for assignment in assignments:
        versions = list(
            db.scalars(
                select(SubmissionVersion)
                .join(Submission)
                .where(Submission.assignment_id == assignment.id, Submission.student_id == user_id)
                .order_by(SubmissionVersion.version_no.desc())
            )
        )
        submitted += bool(versions)
        for version in versions:
            revision = db.scalar(
                select(GradeRevision)
                .where(
                    GradeRevision.submission_version_id == version.id,
                    GradeRevision.status == "published",
                )
                .order_by(GradeRevision.revision_no.desc())
                .limit(1)
            )
            if revision and revision.grade is not None and revision.published_at is not None:
                grades.append(
                    Grade(
                        assignment_id=assignment.id,
                        title=assignment.title,
                        grade=float(revision.grade),
                        published_at=revision.published_at,
                    )
                )
                break
    questions = list(
        db.scalars(
            select(PracticeQuestion).where(
                PracticeQuestion.class_id == class_id,
                PracticeQuestion.status == "published",
            )
        )
    )
    attempts = list(
        db.scalars(
            select(PracticeAttempt)
            .join(PracticeQuestion)
            .where(
                PracticeQuestion.class_id == class_id,
                PracticeQuestion.status == "published",
                PracticeAttempt.student_id == user_id,
            )
            .order_by(
                PracticeAttempt.submitted_at.desc(),
                PracticeAttempt.created_at.desc(),
                PracticeAttempt.id.desc(),
            )
        )
    )
    latest = {a.question_id: a for a in reversed(attempts)}
    mcq = [latest[q.id] for q in questions if q.kind == "mcq" and q.id in latest]
    return ProgressResponse(
        activity=Activity(
            materials_opened=len(
                {e.ref_id for e in events if e.type == "material_opened"} & material_ids
            ),
            materials_available=len(material_ids),
            questions_asked=sum(e.type == "question_asked" for e in events),
            citations_opened=sum(e.type == "citation_opened" for e in events),
            last_activity_at=max((e.occurred_at for e in events), default=None),
        ),
        results=Results(
            assignments_submitted=submitted,
            assignments_available=len(assignments),
            grades=grades,
            practice_attempted=len(latest),
            practice_available=len(questions),
            practice_mcq_attempted=len(mcq),
            practice_mcq_correct_last=sum(a.is_correct is True for a in mcq),
        ),
    )
