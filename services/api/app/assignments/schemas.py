from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=20000)
    criteria: str = Field(default="", max_length=5000)
    due_at: AwareDatetime | None = None
    lesson_id: UUID | None = None


class AssignmentUpdate(BaseModel):
    title: str = Field(default="", min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=20000)
    criteria: str = Field(default="", max_length=5000)
    due_at: AwareDatetime | None = None
    lesson_id: UUID | None = None
    status: Literal["draft", "published", "closed"] | None = None

    @model_validator(mode="after")
    def non_nullable_fields(self) -> Self:
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class AssignmentResponse(AssignmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    class_id: UUID
    status: Literal["draft", "published", "closed"]
    submission_count: int = 0
    my_versions: int = 0
    my_last_submitted_at: datetime | None = None
    my_is_late: bool = False
    my_grade_published: bool = False


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    idempotency_key: str = Field(min_length=8, max_length=100)


class GradeCreate(BaseModel):
    grade: Decimal | None = Field(default=None, ge=0, le=10, decimal_places=2)
    comment: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def require_feedback(self) -> Self:
        if self.grade is None and not self.comment.strip():
            raise ValueError("grade or comment is required")
        return self
