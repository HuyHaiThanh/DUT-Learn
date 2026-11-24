from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import idempotency
from app.assignments.models import Assignment, GradeRevision, Submission, SubmissionVersion
from app.assignments.schemas import AssignmentResponse, GradeCreate, SubmissionCreate
from app.auth.models import User
from app.courses.models import ClassMember, Lesson
from app.deps import ClassRole, class_role, require_class_member
from app.errors import APIError
from app.progress.events import record_event


def access(db: Session, user: User, class_id: UUID, role: ClassRole | None = None) -> None:
    require_class_member(class_id, db, user)
    if role is not None and class_role(db, user, class_id) != role:
        raise HTTPException(403)


def assignment(db: Session, user: User, id: UUID, role: ClassRole | None = None) -> Assignment:
    item = db.scalar(select(Assignment).where(Assignment.id == id).with_for_update())
    if item is None:
        raise HTTPException(404)
    access(db, user, item.class_id, role)
    if item.status == "draft" and class_role(db, user, item.class_id) == "student":
        raise HTTPException(404)
    return item


def lesson_check(db: Session, class_id: UUID, lesson_id: UUID | None) -> None:
    if lesson_id is not None:
        lesson = db.get(Lesson, lesson_id)
        if lesson is None or lesson.class_id != class_id:
            raise HTTPException(404)


def versions(db: Session, item: Assignment, student_id: UUID) -> list[SubmissionVersion]:
    return list(
        db.scalars(
            select(SubmissionVersion)
            .join(Submission)
            .where(Submission.assignment_id == item.id, Submission.student_id == student_id)
            .order_by(SubmissionVersion.version_no)
        )
    )


def revisions(db: Session, version_id: UUID, published: bool = False) -> list[GradeRevision]:
    query = select(GradeRevision).where(GradeRevision.submission_version_id == version_id)
    if published:
        query = query.where(GradeRevision.status == "published")
    return list(db.scalars(query.order_by(GradeRevision.revision_no)))


def grade_data(item: GradeRevision) -> dict[str, Any]:
    return {
        "revision_id": item.id,
        "revision_no": item.revision_no,
        "status": item.status,
        "grade": float(item.grade) if item.grade is not None else None,
        "comment": item.comment,
        "criteria_snapshot": item.criteria_snapshot,
        "published_at": item.published_at,
        "published_by": item.published_by,
    }


def version_data(item: Assignment, version: SubmissionVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "version_id": version.id,
        "version_no": version.version_no,
        "content": version.content,
        "submitted_at": version.submitted_at,
        "is_late": item.due_at is not None and version.submitted_at > item.due_at,
    }


def summary(db: Session, user: User, item: Assignment) -> AssignmentResponse:
    result = AssignmentResponse.model_validate(item)
    if class_role(db, user, item.class_id) == "student":
        own = versions(db, item, user.id)
        result.my_versions = len(own)
        if own:
            result.my_last_submitted_at = own[-1].submitted_at
            result.my_is_late = bool(version_data(item, own[-1])["is_late"])
            result.my_grade_published = any(revisions(db, v.id, True) for v in own)
    else:
        result.submission_count = len(
            list(db.scalars(select(Submission.id).where(Submission.assignment_id == item.id)))
        )
    return result


def submit(db: Session, user: User, item: Assignment, body: SubmissionCreate) -> dict[str, Any]:
    payload = {"assignment_id": str(item.id), "content": body.content}
    existing = idempotency.find(db, user.id, "submission", body.idempotency_key, payload)
    if existing:
        old = db.get(SubmissionVersion, existing[1])
        if old is None:
            raise HTTPException(404)
        return version_data(item, old)
    if item.status != "published":
        raise APIError(409, "assignment_closed", "Bài tập đã đóng nộp.")
    submission = db.scalar(
        select(Submission).where(
            Submission.assignment_id == item.id, Submission.student_id == user.id
        )
    )
    if submission is None:
        submission = Submission(assignment_id=item.id, student_id=user.id)
        db.add(submission)
        db.flush()
    own = versions(db, item, user.id)
    version = SubmissionVersion(
        submission_id=submission.id,
        version_no=len(own) + 1,
        content=body.content,
        submitted_at=datetime.now(UTC),
    )
    db.add(version)
    db.flush()
    idempotency.remember(
        db, user.id, "submission", body.idempotency_key, payload, "submission_version", version.id
    )
    record_event(db, user.id, item.class_id, "submission_created", "submission_version", version.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = idempotency.find(db, user.id, "submission", body.idempotency_key, payload)
        if existing is None:
            raise
        old = db.get(SubmissionVersion, existing[1])
        if old is None:
            raise HTTPException(404)
        return version_data(item, old)
    return version_data(item, version)


def version_access(db: Session, user: User, id: UUID) -> tuple[Assignment, SubmissionVersion]:
    version = db.scalar(
        select(SubmissionVersion).where(SubmissionVersion.id == id).with_for_update()
    )
    if version is None:
        raise HTTPException(404)
    submission = db.get(Submission, version.submission_id)
    if submission is None:
        raise HTTPException(404)
    return assignment(db, user, submission.assignment_id, "lecturer"), version


def save_grade(db: Session, user: User, id: UUID, body: GradeCreate) -> dict[str, Any]:
    item, version = version_access(db, user, id)
    history = revisions(db, version.id)
    if history and history[-1].status == "draft":
        revision = history[-1]
    else:
        revision = GradeRevision(
            submission_version_id=id,
            revision_no=len(history) + 1,
            criteria_snapshot=item.criteria,
            created_by=user.id,
            status="draft",
        )
        db.add(revision)
    revision.criteria_snapshot = item.criteria
    revision.grade = body.grade
    revision.comment = body.comment
    db.commit()
    return grade_data(revision)


def roster(db: Session, item: Assignment) -> list[dict[str, Any]]:
    students = db.scalars(
        select(User)
        .join(ClassMember, ClassMember.user_id == User.id)
        .where(ClassMember.class_id == item.class_id, ClassMember.role == "student")
        .order_by(User.full_name, User.id)
    )
    result = []
    for student in students:
        own = versions(db, item, student.id)
        history = revisions(db, own[-1].id) if own else []
        result.append(
            {
                "student": {
                    "id": student.id,
                    "full_name": student.full_name,
                    "email": student.email,
                },
                "versions": [
                    {
                        key: value
                        for key, value in version_data(item, v).items()
                        if key in {"id", "version_no", "submitted_at", "is_late"}
                    }
                    for v in own
                ],
                "latest_grade": grade_data(history[-1]) if history else None,
            }
        )
    return result
