from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
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
