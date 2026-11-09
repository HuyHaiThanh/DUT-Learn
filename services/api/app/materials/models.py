"""Shared material schema (migration 0003); owned by Tech Lead, tasks add logic not columns."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Record
from app.db import Base

MaterialKind = Literal["pdf", "text"]
Visibility = Literal["students", "lecturers"]
VersionStatus = Literal[
    "uploaded", "processing", "ready", "failed", "published", "superseded", "revoked"
]


class Material(Record, Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("kind IN ('pdf', 'text')", name="ck_materials_kind"),
        CheckConstraint("visibility IN ('students', 'lecturers')", name="ck_materials_visibility"),
    )
    class_id: Mapped[UUID] = mapped_column(ForeignKey("classes.id"), index=True)
    lesson_id: Mapped[UUID | None] = mapped_column(ForeignKey("lessons.id"))
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[MaterialKind] = mapped_column(Text)
    visibility: Mapped[Visibility] = mapped_column(Text, server_default="students")
    source_note: Mapped[str | None] = mapped_column(Text)
    license_note: Mapped[str | None] = mapped_column(Text)
    active_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("material_versions.id", use_alter=True, name="fk_materials_active_version")
    )


class MaterialVersion(Record, Base):
    __tablename__ = "material_versions"
    __table_args__ = (UniqueConstraint("material_id", "version_no"),)
    material_id: Mapped[UUID] = mapped_column(ForeignKey("materials.id"))
    version_no: Mapped[int]
    status: Mapped[VersionStatus] = mapped_column(Text, server_default="uploaded")
    storage_key: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    page_count: Mapped[int | None]
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class Chunk(Record, Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("version_id", "ordinal"),)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("material_versions.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int]
    kind: Mapped[Literal["text", "code"]] = mapped_column(Text, server_default="text")
    page_index: Mapped[int]
    page_index_end: Mapped[int]
    page_label: Mapped[str | None] = mapped_column(Text)
    char_start: Mapped[int]
    char_end: Mapped[int]
    code_block_id: Mapped[str | None] = mapped_column(Text)
    part_no: Mapped[int | None]
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
