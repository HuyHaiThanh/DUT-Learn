import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base
from app.errors import APIError

Operation = Literal["submission", "practice_attempt"]


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "key"),
        CheckConstraint(
            "operation IN ('submission', 'practice_attempt')", name="ck_idempotency_operation"
        ),
        CheckConstraint("length(key) BETWEEN 8 AND 100", name="ck_idempotency_key_length"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[Operation] = mapped_column(Text)
    key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    response_ref_type: Mapped[str] = mapped_column(Text)
    response_ref_id: Mapped[UUID]


def validate_key(key: str) -> None:
    if not isinstance(key, str) or not 8 <= len(key) <= 100:
        raise APIError(422, "validation_error", "Khóa chống trùng phải có từ 8 đến 100 ký tự.")


def payload_hash(payload: Mapping[str, Any]) -> str:
    body = {name: value for name, value in payload.items() if name != "idempotency_key"}
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def find(
    db: Session, user_id: UUID, operation: Operation, key: str, payload: Mapping[str, Any]
) -> tuple[str, UUID] | None:
    validate_key(key)
    stored = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
            IdempotencyKey.key == key,
        )
    )
    if stored is None:
        return None
    if stored.payload_hash != payload_hash(payload):
        raise APIError(
            409, "idempotency_conflict", "Khóa chống trùng đã được dùng với dữ liệu khác."
        )
    return stored.response_ref_type, stored.response_ref_id


def remember(
    db: Session,
    user_id: UUID,
    operation: Operation,
    key: str,
    payload: Mapping[str, Any],
    ref_type: str,
    ref_id: UUID,
) -> None:
    """Add the key in the caller's transaction; unique conflicts must roll it back."""
    validate_key(key)
    db.add(
        IdempotencyKey(
            user_id=user_id,
            operation=operation,
            key=key,
            payload_hash=payload_hash(payload),
            response_ref_type=ref_type,
            response_ref_id=ref_id,
        )
    )
