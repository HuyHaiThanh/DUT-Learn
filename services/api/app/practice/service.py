from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import idempotency
from app.auth.models import User
from app.courses.models import Class, Lesson
from app.deps import class_role, require_class_lecturer, require_class_member
from app.errors import APIError
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.practice.schemas import (
    AttemptCreate,
    AttemptResult,
    QuestionCreate,
    QuestionPatch,
)
from app.progress.events import record_event


def question_for_member(db: Session, user: User, question_id: UUID) -> PracticeQuestion:
    question = db.scalar(
        select(PracticeQuestion).where(PracticeQuestion.id == question_id).with_for_update()
    )
    if question is None:
        raise HTTPException(404)
    require_class_member(question.class_id, db, user)
    return question


def lecturer_question(db: Session, user: User, question_id: UUID) -> PracticeQuestion:
    question = question_for_member(db, user, question_id)
    classroom = require_class_member(question.class_id, db, user)
    require_class_lecturer(classroom, db, user)
    return question


def require_student(db: Session, user: User, question: PracticeQuestion) -> None:
    if class_role(db, user, question.class_id) != "student":
        raise HTTPException(403)


def validate_lesson(db: Session, class_id: UUID, lesson_id: UUID | None) -> None:
    if lesson_id is not None:
        lesson = db.get(Lesson, lesson_id)
        if lesson is None or lesson.class_id != class_id:
            raise HTTPException(404)


def create_question(
    db: Session, user: User, class_id: UUID, data: QuestionCreate
) -> PracticeQuestion:
    validate_lesson(db, class_id, data.lesson_id)
    question = PracticeQuestion(
        **data.model_dump(),
        class_id=class_id,
        created_by=user.id,
        origin="lecturer",
        status="draft",
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def invalid_transition() -> APIError:
    return APIError(409, "invalid_transition", "Không thể chuyển trạng thái câu hỏi.")


def bump_content_version(db: Session, class_id: UUID) -> None:
    db.execute(
        update(Class)
        .where(Class.id == class_id)
        .values(
            content_version=Class.content_version + 1,
        )
    )


def update_question(
    db: Session, user: User, question: PracticeQuestion, data: QuestionPatch
) -> PracticeQuestion:
    if question.status == "retired":
        raise invalid_transition()
    changes = data.model_dump(exclude_unset=True)
    try:
        validated = QuestionCreate.model_validate(
            {
                **{name: getattr(question, name) for name in QuestionCreate.model_fields},
                **changes,
            }
        )
    except ValidationError:
        raise APIError(422, "validation_error", "Dữ liệu câu hỏi không hợp lệ.") from None
    validate_lesson(db, question.class_id, validated.lesson_id)
    if question.status == "published":
        previous = question
        question = PracticeQuestion(
            **validated.model_dump(),
            class_id=previous.class_id,
            created_by=user.id,
            origin=previous.origin,
            status="published",
            supersedes_id=previous.id,
            published_at=datetime.now(UTC),
            source_chunk_id=previous.source_chunk_id,
            source_version_id=previous.source_version_id,
            approved_by=previous.approved_by,
            approved_at=previous.approved_at,
        )
        previous.status = "retired"
        db.add(question)
        bump_content_version(db, question.class_id)
    else:
        for name, value in validated.model_dump().items():
            setattr(question, name, value)
        if question.origin == "ai" and question.status == "approved" and changes:
            question.status = "draft"
            question.approved_by = None
            question.approved_at = None
    db.commit()
    db.refresh(question)
    return question


def transition(
    db: Session, user: User, question: PracticeQuestion, action: str
) -> PracticeQuestion:
    if action == "approve" and question.origin == "ai" and question.status == "draft":
        question.status = "approved"
        question.approved_by = user.id
        question.approved_at = datetime.now(UTC)
    elif action == "publish" and (
        (question.origin == "lecturer" and question.status == "draft")
        or (question.origin == "ai" and question.status == "approved")
    ):
        question.status = "published"
        question.published_at = datetime.now(UTC)
    elif action == "retire" and question.status == "published":
        question.status = "retired"
    else:
        raise invalid_transition()
    if action in {"publish", "retire"}:
        bump_content_version(db, question.class_id)
    db.commit()
    db.refresh(question)
    return question


def attempt_result(attempt: PracticeAttempt) -> AttemptResult:
    return AttemptResult(
        attempt_id=attempt.id,
        is_correct=attempt.is_correct,
        answer_key=attempt.question_snapshot["answer_key"],
        explanation=attempt.question_snapshot["explanation"],
        submitted_at=attempt.submitted_at,
    )


def submit_attempt(
    db: Session, user: User, question: PracticeQuestion, data: AttemptCreate
) -> AttemptResult:
    require_student(db, user, question)
    payload = {"question_id": str(question.id), "response": data.response}

    def replay() -> AttemptResult | None:
        stored = idempotency.find(db, user.id, "practice_attempt", data.idempotency_key, payload)
        if stored is None:
            return None
        attempt = db.get(PracticeAttempt, stored[1])
        if attempt is None:
            raise HTTPException(404)
        return attempt_result(attempt)

    existing = replay()
    if existing is not None:
        return existing
    if question.status != "published":
        raise HTTPException(404)
    if not data.response.strip() or (
        question.kind == "mcq"
        and data.response not in {str(i) for i in range(len(question.options or []))}
    ):
        raise APIError(422, "validation_error", "Câu trả lời không hợp lệ.")
    attempt = PracticeAttempt(
        question_id=question.id,
        student_id=user.id,
        response=data.response,
        question_snapshot={
            name: getattr(question, name)
            for name in (
                "kind",
                "stem",
                "options",
                "answer_key",
                "explanation",
            )
        },
        is_correct=data.response == question.answer_key if question.kind == "mcq" else None,
    )
    try:
        db.add(attempt)
        db.flush()
        idempotency.remember(
            db,
            user.id,
            "practice_attempt",
            data.idempotency_key,
            payload,
            "practice_attempt",
            attempt.id,
        )
        record_event(
            db, user.id, question.class_id, "practice_attempted", "practice_question", question.id
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = replay()
        if existing is not None:
            return existing
        raise
    db.refresh(attempt)
    return attempt_result(attempt)
