from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class, ClassMember, Course
from app.db import get_db
from app.deps import class_role, require_class_lecturer, require_class_member, require_user
from app.materials.models import Chunk, Material, MaterialVersion
from app.materials.policy import can_read_version
from app.progress.models import ReadingPosition
from app.progress.schemas import EventInput, ProgressResponse, StudentProgress
from app.progress.service import receive_event, student_progress

router = APIRouter(prefix="/api", tags=["reading"])


@router.post("/events", status_code=204)
def post_event(
    data: EventInput, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> Response:
    receive_event(db, user, data)
    return Response(status_code=204)


@router.get("/classes/{class_id}/progress/me", response_model=ProgressResponse)
def my_progress(
    response: Response,
    classroom: Class = Depends(require_class_member),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> ProgressResponse:
    if class_role(db, user, classroom.id) != "student":
        raise HTTPException(403)
    response.headers["Cache-Control"] = "private, no-store"
    return student_progress(db, classroom.id, user.id)


@router.get("/classes/{class_id}/progress", response_model=list[StudentProgress])
def class_progress(
    response: Response,
    classroom: Class = Depends(require_class_lecturer),
    db: Session = Depends(get_db),
) -> list[StudentProgress]:
    response.headers["Cache-Control"] = "private, no-store"
    students = db.scalars(
        select(User)
        .join(ClassMember)
        .where(
            ClassMember.class_id == classroom.id,
            ClassMember.role == "student",
        )
        .order_by(User.full_name, User.id)
    )
    rows = []
    for student in students:
        progress = student_progress(db, classroom.id, student.id)
        rows.append(
            StudentProgress(
                **progress.model_dump(),
                user_id=student.id,
                full_name=student.full_name,
                last_activity_at=progress.activity.last_activity_at,
            )
        )
    return rows


class PositionInput(BaseModel):
    material_id: UUID
    version_id: UUID
    page_index: int = Field(ge=0, strict=True)


class ContinueResponse(PositionInput):
    material_title: str
    class_id: UUID
    course_name: str
    page_label: str
    updated_at: datetime


@router.put("/reading-position", status_code=204)
def save_position(
    data: PositionInput, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> Response:
    # Shared locks keep publication/revocation from changing the source before commit.
    material = db.scalar(
        select(Material).where(Material.id == data.material_id).with_for_update(read=True)
    )
    version = db.scalar(
        select(MaterialVersion)
        .where(MaterialVersion.id == data.version_id)
        .with_for_update(read=True)
    )
    if (
        material is None
        or version is None
        or version.material_id != material.id
        or material.active_version_id != version.id
        or not can_read_version(db, user, version)
    ):
        raise HTTPException(404)
    if version.page_count is None or data.page_index >= version.page_count:
        raise HTTPException(422)
    statement = insert(ReadingPosition).values(user_id=user.id, **data.model_dump())
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[ReadingPosition.user_id, ReadingPosition.material_id],
            set_={
                "version_id": data.version_id,
                "page_index": data.page_index,
                "updated_at": func.clock_timestamp(),
            },
        )
    )
    db.commit()
    return Response(status_code=204)


@router.get("/me/continue", response_model=ContinueResponse | None)
def continue_reading(
    response: Response, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> ContinueResponse | None:
    response.headers["Cache-Control"] = "private, no-store"
    rows = db.execute(
        select(ReadingPosition, Material, MaterialVersion, Class, Course)
        .join(Material, Material.id == ReadingPosition.material_id)
        .join(MaterialVersion, MaterialVersion.id == ReadingPosition.version_id)
        .join(Class, Class.id == Material.class_id)
        .join(Course, Course.id == Class.course_id)
        .where(
            ReadingPosition.user_id == user.id,
            Material.active_version_id == MaterialVersion.id,
            MaterialVersion.status == "published",
            Class.status == "open",
        )
        .order_by(ReadingPosition.updated_at.desc(), ReadingPosition.material_id)
    )
    for position, material, version, classroom, course in rows:
        if not can_read_version(db, user, version):
            continue
        label = db.scalar(
            select(Chunk.page_label)
            .where(
                Chunk.version_id == version.id,
                Chunk.page_index == position.page_index,
            )
            .order_by(Chunk.ordinal)
            .limit(1)
        )
        return ContinueResponse(
            material_id=material.id,
            material_title=material.title,
            class_id=classroom.id,
            course_name=course.name,
            version_id=version.id,
            page_index=position.page_index,
            page_label=label or str(position.page_index + 1),
            updated_at=position.updated_at,
        )
    return None
