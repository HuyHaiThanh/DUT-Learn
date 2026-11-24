from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    class_id: UUID
    lesson_id: UUID | None = None
    material_id: UUID | None = None
    page_index: int | None = Field(default=None, ge=0)
    session_id: UUID | None = None
    mode: Literal["answer", "hint"] = "answer"
    question: str

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 2000:
            raise ValueError("Câu hỏi phải có từ 1 đến 2000 ký tự.")
        return value


class CitationResponse(BaseModel):
    id: UUID
    ordinal: int
    material_id: UUID
    material_title: str
    version_id: UUID
    page_index: int
    page_label: str | None
    excerpt: str


class AskResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    status: Literal["ok", "insufficient_evidence"]
    answer: str
    citations: list[CitationResponse]
    limitation: str | None
    retriever: str
    model: str
    latency_ms: int
    request_id: str


class SessionResponse(BaseModel):
    id: UUID
    lesson_id: UUID | None
    material_id: UUID | None
    created_at: datetime
    last_question: str | None
    message_count: int


class MessageResponse(BaseModel):
    id: UUID
    role: str
    mode: str
    content: str | None
    status: str
    error_code: str | None
    created_at: datetime
    citations: list[CitationResponse]
    notice: str | None = None
    model: str | None = None


class CitationOpenResponse(BaseModel):
    version_id: UUID
    material_id: UUID
    page_index: int
    page_label: str | None
    excerpt: str
    char_start: int
    char_end: int
