from uuid import UUID

from sqlalchemy.orm import Session

from app.progress.models import LearningEvent, LearningEventType


def record_event(
    db: Session,
    user_id: UUID,
    class_id: UUID,
    type: LearningEventType,
    ref_type: str | None = None,
    ref_id: UUID | None = None,
) -> None:
    """Add an event after the caller has checked access, without committing."""
    db.add(
        LearningEvent(
            user_id=user_id, class_id=class_id, type=type, ref_type=ref_type, ref_id=ref_id
        )
    )
