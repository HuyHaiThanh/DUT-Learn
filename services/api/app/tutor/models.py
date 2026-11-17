from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Record
from app.db import Base


class ChatSession(Record, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (Index("ix_chat_sessions_user_class", "user_id", "class_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    class_id: Mapped[UUID] = mapped_column(ForeignKey("classes.id"))
    lesson_id: Mapped[UUID | None] = mapped_column(ForeignKey("lessons.id"))
    material_id: Mapped[UUID | None] = mapped_column(ForeignKey("materials.id"))


class ChatMessage(Record, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_role"),
        CheckConstraint("mode IN ('answer', 'hint')", name="ck_chat_mode"),
        CheckConstraint(
            "status IN ('ok', 'insufficient_evidence', 'error')", name="ck_chat_status"
        ),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )
    session_id: Mapped[UUID] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    retriever: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int]
    request_id: Mapped[str] = mapped_column(Text)


class Citation(Record, Base):
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("message_id", "ordinal"),)
    message_id: Mapped[UUID] = mapped_column(ForeignKey("chat_messages.id"), index=True)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("chunks.id"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("material_versions.id"))
    page_index: Mapped[int]
    excerpt: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int]
