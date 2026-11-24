from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assignments import service
from app.assignments.models import Assignment, GradeRevision, Submission
from app.assignments.schemas import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
    GradeCreate,
    SubmissionCreate,
)
from app.auth.models import User
from app.db import get_db
from app.deps import class_role, get_current_user
from app.errors import APIError

router = APIRouter(prefix="/api", tags=["assignments"])


@router.get("/classes/{class_id}/assignments")
def list_assignments(
    class_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AssignmentResponse]:
    service.access(db, user, class_id)
    query = select(Assignment).where(Assignment.class_id == class_id)
    if class_role(db, user, class_id) == "student":
        query = query.where(Assignment.status != "draft")
    return [
        service.summary(db, user, item)
        for item in db.scalars(query.order_by(Assignment.created_at, Assignment.id))
    ]


@router.post("/classes/{class_id}/assignments", status_code=201)
def create_assignment(
    class_id: UUID,
    body: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentResponse:
    service.access(db, user, class_id, "lecturer")
    service.lesson_check(db, class_id, body.lesson_id)
    item = Assignment(**body.model_dump(), class_id=class_id, created_by=user.id, status="draft")
    db.add(item)
    db.commit()
    return service.summary(db, user, item)


@router.get("/assignments/{id}")
def get_assignment(
    id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AssignmentResponse:
    return service.summary(db, user, service.assignment(db, user, id))


@router.patch("/assignments/{id}")
def update_assignment(
    id: UUID,
    body: AssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentResponse:
    item = service.assignment(db, user, id, "lecturer")
    values = body.model_dump(exclude_unset=True)
    if "lesson_id" in values:
        service.lesson_check(db, item.class_id, body.lesson_id)
    if "status" in values and (item.status, body.status) not in {
        ("draft", "published"),
        ("published", "closed"),
        ("closed", "published"),
    }:
        raise APIError(409, "invalid_transition", "Không thể chuyển trạng thái bài tập.")
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    return service.summary(db, user, item)


@router.delete("/assignments/{id}", status_code=204)
def delete_assignment(
    id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    item = service.assignment(db, user, id, "lecturer")
    if (
        item.status != "draft"
        or db.scalar(select(Submission.id).where(Submission.assignment_id == id)) is not None
    ):
        raise APIError(409, "invalid_transition", "Chỉ xóa bài tập nháp chưa có bài nộp.")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/assignments/{id}/submissions")
def submit(
    id: UUID,
    body: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return service.submit(db, user, service.assignment(db, user, id, "student"), body)


@router.get("/assignments/{id}/submissions/me")
def my_submissions(
    id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    item = service.assignment(db, user, id, "student")
    result = []
    for version in service.versions(db, item, user.id):
        history = service.revisions(db, version.id, True)
        grade = history[-1] if history else None
        result.append(
            {
                **{
                    key: value
                    for key, value in service.version_data(item, version).items()
                    if key != "id"
                },
                "grade": {
                    "revision_id": grade.id,
                    "grade": float(grade.grade) if grade.grade is not None else None,
                    "comment": grade.comment,
                    "published_at": grade.published_at,
                }
                if grade
                else None,
            }
        )
    return result


@router.get("/assignments/{id}/submissions")
def submissions(
    id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    return service.roster(db, service.assignment(db, user, id, "lecturer"))


@router.get("/submission-versions/{id}")
def submission_version(
    id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    item, version = service.version_access(db, user, id)
    return {
        **service.version_data(item, version),
        "revisions": [service.grade_data(r) for r in service.revisions(db, id)],
    }


@router.post("/submission-versions/{id}/grades")
def save_grade(
    id: UUID,
    body: GradeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return service.save_grade(db, user, id, body)


@router.post("/grade-revisions/{id}/publish")
def publish_grade(
    id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    revision = db.get(GradeRevision, id)
    if revision is None:
        raise HTTPException(404)
    service.version_access(db, user, revision.submission_version_id)
    db.refresh(revision)
    if revision.status != "draft":
        raise APIError(409, "invalid_transition", "Bản chấm đã được công bố.")
    revision.status = "published"
    revision.published_at = datetime.now(UTC)
    revision.published_by = user.id
    db.commit()
    return service.grade_data(revision)
