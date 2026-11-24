from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class EventInput(BaseModel):
    class_id: UUID
    type: Literal["material_opened", "citation_opened", "feedback_viewed"]
    ref_id: UUID


class Activity(BaseModel):
    materials_opened: int
    materials_available: int
    questions_asked: int
    citations_opened: int
    last_activity_at: datetime | None


class Grade(BaseModel):
    assignment_id: UUID
    title: str
    grade: float
    published_at: datetime


class Results(BaseModel):
    assignments_submitted: int
    assignments_available: int
    grades: list[Grade]
    practice_attempted: int
    practice_available: int
    practice_mcq_correct_last: int
    practice_mcq_attempted: int


class ProgressResponse(BaseModel):
    activity: Activity
    results: Results


class StudentProgress(ProgressResponse):
    user_id: UUID
    full_name: str
    last_activity_at: datetime | None
