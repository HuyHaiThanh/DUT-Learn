from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Stem = Annotated[str, Field(min_length=1, max_length=5000)]
Option = Annotated[str, Field(min_length=1, max_length=1000)]
Options = Annotated[list[Option], Field(min_length=2, max_length=6)]


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mcq", "short"]
    stem: Stem
    options: Options | None = None
    answer_key: Stem
    explanation: str = Field(default="", max_length=5000)
    lesson_id: UUID | None = None

    @model_validator(mode="after")
    def validate_answer(self) -> Self:
        if not self.stem.strip() or not self.answer_key.strip():
            raise ValueError("Question and answer must not be blank")
        if self.kind == "mcq":
            if (
                self.options is None
                or len({s.strip() for s in self.options}) != len(self.options)
                or any(not s.strip() for s in self.options)
            ):
                raise ValueError("MCQ options must be distinct and nonblank")
            if self.answer_key not in {str(i) for i in range(len(self.options))}:
                raise ValueError("Invalid answer index")
        elif self.options is not None:
            raise ValueError("Short questions must have null options")
        return self


class QuestionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mcq", "short"] | None = None
    stem: Stem | None = None
    options: Options | None = None
    answer_key: Stem | None = None
    explanation: Annotated[str, Field(max_length=5000)] | None = None
    lesson_id: UUID | None = None


class QuestionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    lesson_id: UUID | None
    kind: Literal["mcq", "short"]
    stem: str
    options: list[str] | None


class LecturerQuestion(QuestionView):
    answer_key: str
    explanation: str
    origin: Literal["ai", "lecturer"]
    status: Literal["draft", "approved", "published", "retired"]
    supersedes_id: UUID | None


class StudentQuestion(QuestionView):
    my_attempts: int
    my_last_correct: bool | None


class AttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: Stem
    idempotency_key: str = Field(min_length=8, max_length=100)


class AttemptResult(BaseModel):
    attempt_id: UUID
    is_correct: bool | None
    answer_key: str
    explanation: str
    submitted_at: datetime


class AttemptHistory(AttemptResult):
    response: str
    question_snapshot: dict[str, object]
