from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class, Lesson
from app.courses.schemas import ClassDetail, LessonCreate, LessonUpdate, LessonView, MyClassView
from app.courses.service import class_detail, create_lesson, my_classes, update_lesson
from app.db import get_db
from app.deps import get_current_user, require_class_lecturer, require_class_member

router = APIRouter(prefix="/api", tags=["classes"])


@router.get("/classes", response_model=list[MyClassView])
def list_classes(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[MyClassView]:
    return my_classes(db, user)


@router.get("/classes/{class_id}", response_model=ClassDetail)
def get_class(
    classroom: Class = Depends(require_class_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassDetail:
    return class_detail(db, user, classroom)


@router.post("/classes/{class_id}/lessons", response_model=LessonView, status_code=201)
def post_lesson(
    data: LessonCreate,
    classroom: Class = Depends(require_class_lecturer),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Lesson:
    return create_lesson(db, user, classroom, data)


def lesson_for_lecturer(
    lesson_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404)
    classroom = require_class_member(lesson.class_id, db, user)
    require_class_lecturer(classroom, db, user)
    return lesson


@router.patch("/lessons/{lesson_id}", response_model=LessonView)
def patch_lesson(
    data: LessonUpdate,
    lesson: Lesson = Depends(lesson_for_lecturer),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Lesson:
    return update_lesson(db, user, lesson, data)
