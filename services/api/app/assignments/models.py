from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Record
from app.db import Base


class Assignment(Record, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'closed')", name="ck_assignments_status"),
    )
    class_id: Mapped[UUID] = mapped_column(ForeignKey("classes.id"), index=True)
    lesson_id: Mapped[UUID | None] = mapped_column(ForeignKey("lessons.id"))
    title: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    criteria: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[Literal["draft", "published", "closed"]] = mapped_column(
        Text, server_default="draft"
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class Submission(Record, Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    assignment_id: Mapped[UUID] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class SubmissionVersion(Base):
    __tablename__ = "submission_versions"
    __table_args__ = (
        UniqueConstraint("submission_id", "version_no"),
        CheckConstraint("version_no >= 1", name="ck_submission_versions_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"))
    version_no: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GradeRevision(Record, Base):
    __tablename__ = "grade_revisions"
    __table_args__ = (
        UniqueConstraint("submission_version_id", "revision_no"),
        CheckConstraint("revision_no >= 1", name="ck_grade_revisions_revision"),
        CheckConstraint("grade BETWEEN 0 AND 10", name="ck_grade_revisions_grade"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_grade_revisions_status"),
    )
    submission_version_id: Mapped[UUID] = mapped_column(ForeignKey("submission_versions.id"))
    revision_no: Mapped[int]
    grade: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    comment: Mapped[str] = mapped_column(Text)
    criteria_snapshot: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[Literal["draft", "published"]] = mapped_column(Text, server_default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
