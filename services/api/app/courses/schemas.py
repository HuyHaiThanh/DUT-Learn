from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.admin.schemas import ClassView


class MyClassView(ClassView):
    course_code: str
    course_name: str
    role: Literal["lecturer", "student"]


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LessonCreate(BaseModel):
    title: Title
    position: int = Field(default=0, ge=0)


class LessonUpdate(BaseModel):
    title: Title | None = None
    position: int | None = Field(default=None, ge=0)
    is_published: bool | None = None

    @model_validator(mode="after")
    def reject_null(self) -> "LessonUpdate":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Lesson fields cannot be null")
        return self


class LessonView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    position: int
    is_published: bool


class ClassDetail(MyClassView):
    lessons: list[LessonView]
