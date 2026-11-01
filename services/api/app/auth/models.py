from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Record:
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Record, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        CheckConstraint("system_role IN ('admin', 'user')", name="ck_users_system_role"),
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    system_role: Mapped[Literal["admin", "user"]] = mapped_column(Text, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class SessionToken(Record, Base):
    __tablename__ = "sessions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(Text)


class LoginAttempt(Record, Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_login_attempts_email_lower"),
        Index("ix_login_attempts_email_attempted_at", "email", "attempted_at"),
    )
    email: Mapped[str] = mapped_column(Text)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    succeeded: Mapped[bool] = mapped_column(Boolean)


class AuditEvent(Record, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[UUID]
    detail: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
