from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Record
from app.db import Base


class PracticeQuestion(Record, Base):
    __tablename__ = "practice_questions"
    __table_args__ = (
        CheckConstraint("kind IN ('mcq', 'short')", name="ck_practice_questions_kind"),
        CheckConstraint("origin IN ('ai', 'lecturer')", name="ck_practice_questions_origin"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'published', 'retired')",
            name="ck_practice_questions_status",
        ),
    )
    class_id: Mapped[UUID] = mapped_column(ForeignKey("classes.id"), index=True)
    lesson_id: Mapped[UUID | None] = mapped_column(ForeignKey("lessons.id"))
    kind: Mapped[Literal["mcq", "short"]] = mapped_column(Text)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str] | None] = mapped_column(JSONB)
    answer_key: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    source_chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("chunks.id"))
    source_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("material_versions.id"))
    origin: Mapped[Literal["ai", "lecturer"]] = mapped_column(Text)
    status: Mapped[Literal["draft", "approved", "published", "retired"]] = mapped_column(
        Text, server_default="draft"
    )
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("practice_questions.id"))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"
    __table_args__ = (Index("ix_practice_attempts_question_student", "question_id", "student_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    question_id: Mapped[UUID] = mapped_column(ForeignKey("practice_questions.id"))
    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    question_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    response: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool | None]
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
