"""The single SQL boundary for retrieval and source revalidation (I2)."""

from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class, ClassMember
from app.materials.models import Chunk, Material, MaterialVersion


def scoped_chunks(db: Session, *, user: User, class_id: UUID) -> Select[Chunk]:
    return (
        select(Chunk)
        .join(MaterialVersion, Chunk.version_id == MaterialVersion.id)
        .join(Material, MaterialVersion.material_id == Material.id)
        .join(Class, Material.class_id == Class.id)
        .join(ClassMember, ClassMember.class_id == Class.id)
        .where(
            Chunk.version_id == Material.active_version_id,
            MaterialVersion.status == "published",
            Material.class_id == class_id,
            Class.status == "open",
            ClassMember.user_id == user.id,
            or_(ClassMember.role == "lecturer", Material.visibility == "students"),
        )
    )


def versions_still_valid(
    db: Session, *, user: User, class_id: UUID, version_ids: set[UUID]
) -> set[UUID]:
    statement = scoped_chunks(db, user=user, class_id=class_id)
    return set(
        db.scalars(
            statement.with_only_columns(Chunk.version_id)
            .where(Chunk.version_id.in_(version_ids))
            .distinct()
        )
    )
