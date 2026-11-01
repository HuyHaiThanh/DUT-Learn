from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, User
from app.courses.models import Class, ClassMember, Course
from app.errors import APIError


def save_created(
    db: Session, actor: User, record: User | Course | Class | ClassMember, target_type: str
) -> None:
    try:
        db.add(record)
        db.flush()
        db.add(
            AuditEvent(
                actor_id=actor.id,
                action="create",
                target_type=target_type,
                target_id=record.id,
                detail={},
            )
        )
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, "conflict", "Dữ liệu đã tồn tại hoặc tham chiếu không hợp lệ."
        ) from None


def audit_deleted(db: Session, actor: User, target_id: UUID, target_type: str) -> None:
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="delete",
            target_type=target_type,
            target_id=target_id,
            detail={},
        )
    )
