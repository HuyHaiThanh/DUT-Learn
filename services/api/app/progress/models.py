from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReadingPosition(Base):
    __tablename__ = "reading_positions"
    __table_args__ = (
        UniqueConstraint("user_id", "material_id"),
        CheckConstraint("page_index >= 0", name="ck_reading_positions_page"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    material_id: Mapped[UUID] = mapped_column(ForeignKey("materials.id"), primary_key=True)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("material_versions.id"))
    page_index: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


LearningEventType = Literal[
    "material_opened",
    "question_asked",
    "citation_opened",
    "submission_created",
    "practice_attempted",
    "feedback_viewed",
]


class LearningEvent(Base):
    __tablename__ = "learning_events"
    __table_args__ = (
        CheckConstraint(
            "type IN ('material_opened', 'question_asked', 'citation_opened', "
            "'submission_created', 'practice_attempted', 'feedback_viewed')",
            name="ck_learning_events_type",
        ),
        Index("ix_learning_events_class_user", "class_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    class_id: Mapped[UUID] = mapped_column(ForeignKey("classes.id"))
    type: Mapped[LearningEventType] = mapped_column(Text)
    ref_type: Mapped[str | None] = mapped_column(Text)
    ref_id: Mapped[UUID | None]
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
