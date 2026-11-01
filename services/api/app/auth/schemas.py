from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginInput(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class MembershipView(BaseModel):
    class_id: UUID
    class_code: str
    course_code: str
    course_name: str
    role: Literal["lecturer", "student"]


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str
    system_role: Literal["admin", "user"]


class MeView(UserView):
    classes: list[MembershipView]
