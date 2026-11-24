from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class
from app.db import get_db
from app.deps import class_role, get_current_user, require_class_lecturer, require_class_member
from app.practice import service
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.practice.schemas import (
    AttemptCreate,
    AttemptHistory,
    AttemptResult,
    LecturerQuestion,
    QuestionCreate,
    QuestionPatch,
    StudentQuestion,
)

router = APIRouter(prefix="/api", tags=["practice"])


@router.post("/classes/{class_id}/practice", response_model=LecturerQuestion, status_code=201)
def post_question(
    data: QuestionCreate,
    classroom: Class = Depends(require_class_lecturer),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.create_question(db, user, classroom.id, data)


@router.get("/classes/{class_id}/practice")
def list_questions(
    include_retired: bool = False,
    classroom: Class = Depends(require_class_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LecturerQuestion] | list[StudentQuestion]:
    lecturer = class_role(db, user, classroom.id) == "lecturer"
    query = select(PracticeQuestion).where(PracticeQuestion.class_id == classroom.id)
    if not lecturer:
        query = query.where(PracticeQuestion.status == "published")
    elif not include_retired:
        query = query.where(PracticeQuestion.status != "retired")
    questions = db.scalars(query.order_by(PracticeQuestion.created_at, PracticeQuestion.id)).all()
    if lecturer:
        return [LecturerQuestion.model_validate(q) for q in questions]
    attempts = db.scalars(
        select(PracticeAttempt)
        .join(PracticeQuestion)
        .where(
            PracticeQuestion.class_id == classroom.id,
            PracticeAttempt.student_id == user.id,
        )
        .order_by(PracticeAttempt.submitted_at, PracticeAttempt.id)
    ).all()
    result = []
    for question in questions:
        own = [a for a in attempts if a.question_id == question.id]
        result.append(
            StudentQuestion(
                id=question.id,
                lesson_id=question.lesson_id,
                kind=question.kind,
                stem=question.stem,
                options=question.options,
                my_attempts=len(own),
                my_last_correct=own[-1].is_correct if own else None,
            )
        )
    return result


def lecturer_question(
    question_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.lecturer_question(db, user, question_id)


def member_question(
    question_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.question_for_member(db, user, question_id)


@router.patch("/practice/{question_id}", response_model=LecturerQuestion)
def patch_question(
    data: QuestionPatch,
    question: PracticeQuestion = Depends(lecturer_question),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.update_question(db, user, question, data)


@router.post("/practice/{question_id}/approve", response_model=LecturerQuestion)
def approve_question(
    question: PracticeQuestion = Depends(lecturer_question),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.transition(db, user, question, "approve")


@router.post("/practice/{question_id}/publish", response_model=LecturerQuestion)
def publish_question(
    question: PracticeQuestion = Depends(lecturer_question),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.transition(db, user, question, "publish")


@router.post("/practice/{question_id}/retire", response_model=LecturerQuestion)
def retire_question(
    question: PracticeQuestion = Depends(lecturer_question),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PracticeQuestion:
    return service.transition(db, user, question, "retire")


@router.post("/practice/{question_id}/attempts")
def post_attempt(
    data: AttemptCreate,
    question: PracticeQuestion = Depends(member_question),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptResult:
    return service.submit_attempt(db, user, question, data)


@router.get("/practice/{question_id}/attempts/me")
def own_attempts(
    question: PracticeQuestion = Depends(member_question),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttemptHistory]:
    service.require_student(db, user, question)
    attempts = db.scalars(
        select(PracticeAttempt)
        .where(
            PracticeAttempt.question_id == question.id,
            PracticeAttempt.student_id == user.id,
        )
        .order_by(PracticeAttempt.submitted_at, PracticeAttempt.id)
    ).all()
    return [
        AttemptHistory(
            **service.attempt_result(a).model_dump(),
            response=a.response,
            question_snapshot=a.question_snapshot,
        )
        for a in attempts
    ]
