"""Publication changes serialize on the material and commit with the class epoch."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, User
from app.courses.models import Class, Lesson
from app.errors import APIError
from app.materials.models import Material, MaterialVersion
from app.materials.schemas import MaterialUpdate
from app.materials.service import lecturer_material


def lock_material(db: Session, user: User, material_id: UUID) -> Material:
    lecturer_material(db, user, material_id)
    return db.scalars(
        select(Material)
        .where(Material.id == material_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def bump_content(db: Session, material: Material) -> None:
    db.execute(
        update(Class)
        .where(Class.id == material.class_id)
        .values(content_version=Class.content_version + 1)
    )


def audit(db: Session, user: User, action: str, target_id: UUID, target_type: str) -> None:
    db.add(
        AuditEvent(
            actor_id=user.id, action=action, target_type=target_type, target_id=target_id, detail={}
        )
    )


def change_publication(
    db: Session, user: User, version: MaterialVersion, *, publish: bool
) -> MaterialVersion:
    material = lock_material(db, user, version.material_id)
    # A concurrent publisher may have changed this identity while we waited for the lock.
    db.refresh(version)
    allowed = {"ready"} if publish else {"published", "ready", "superseded"}
    if version.status not in allowed:
        raise APIError(409, "invalid_state", "Trạng thái học liệu không cho phép thao tác này.")
    now = datetime.now(UTC)
    if publish:
        db.execute(
            update(MaterialVersion)
            .where(
                MaterialVersion.material_id == material.id, MaterialVersion.status == "published"
            )
            .values(status="superseded")
        )
        changed = db.scalar(
            update(MaterialVersion)
            .where(MaterialVersion.id == version.id, MaterialVersion.status == "ready")
            .values(status="published", published_at=now, published_by=user.id)
            .returning(MaterialVersion.id)
        )
        if changed is None:
            db.rollback()
            raise APIError(409, "invalid_state", "Chỉ công bố học liệu đã sẵn sàng.")
        material.active_version_id = version.id
        bump_content(db, material)
    else:
        version.status = "revoked"
        version.revoked_at = now
        version.revoked_by = user.id
        if material.active_version_id == version.id:
            material.active_version_id = None
            bump_content(db, material)
    audit(
        db,
        user,
        "material_version.publish" if publish else "material_version.revoke",
        version.id,
        "material_version",
    )
    db.commit()
    db.refresh(version)
    return version


def patch_material(db: Session, user: User, material_id: UUID, data: MaterialUpdate) -> Material:
    material = lock_material(db, user, material_id)
    if "lesson_id" in data.model_fields_set and data.lesson_id is not None:
        lesson = db.get(Lesson, data.lesson_id)
        if lesson is None or lesson.class_id != material.class_id:
            raise HTTPException(404)
    if "visibility" in data.model_fields_set and data.visibility != material.visibility:
        bump_content(db, material)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(material, key, value)
    audit(db, user, "material.update", material.id, "material")
    db.commit()
    db.refresh(material)
    return material
