from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Record
from app.db import Base


class Course(Record, Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class Class(Record, Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("course_id", "code", "term"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_classes_status"),
    )
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"))
    code: Mapped[str] = mapped_column(Text)
    term: Mapped[str] = mapped_column(Text)
    status: Mapped[Literal["open", "closed"]] = mapped_column(Text, server_default="open")
    content_version: Mapped[int] = mapped_column(server_default=text("0"))


class ClassMember(Record, Base):
    __tablename__ = "class_members"
    __table_args__ = (
        UniqueConstraint("class_id", "user_id"),
        CheckConstraint("role IN ('lecturer', 'student')", name="ck_class_members_role"),
    )
    class_id: Mapped[UUID] = mapped_column(ForeignKey("classes.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[Literal["lecturer", "student"]] = mapped_column(Text)
