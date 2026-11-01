from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.auth.schemas import LoginInput, UserView


class UserCreate(LoginInput):
    full_name: str = Field(min_length=1, max_length=200)
    system_role: Literal["admin", "user"] = "user"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not value or "@" not in value or any(c.isspace() for c in value):
            raise ValueError("Invalid email")
        return value


class AdminUserView(UserView):
    is_active: bool


class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class CourseView(CourseCreate):
    id: UUID


class ClassCreate(BaseModel):
    course_id: UUID
    code: str = Field(min_length=1, max_length=100)
    term: str = Field(min_length=1, max_length=100)
    status: Literal["open", "closed"] = "open"


class ClassView(ClassCreate):
    id: UUID
    content_version: int


class MemberCreate(BaseModel):
    user_id: UUID
    role: Literal["lecturer", "student"]


class MemberView(MemberCreate):
    id: UUID
    class_id: UUID
