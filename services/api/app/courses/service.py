from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, User
from app.courses.models import Class, ClassMember, Course, Lesson
from app.courses.schemas import ClassDetail, LessonCreate, LessonUpdate, LessonView, MyClassView
from app.deps import class_role


def my_classes(db: Session, user: User) -> list[MyClassView]:
    rows = db.execute(
        select(Class, Course, ClassMember.role)
        .join(Course, Course.id == Class.course_id)
        .join(ClassMember, ClassMember.class_id == Class.id)
        .where(ClassMember.user_id == user.id, Class.status == "open")
        .order_by(Class.code, Class.id)
    )
    return [
        MyClassView(
            id=c.id,
            course_id=c.course_id,
            code=c.code,
            term=c.term,
            status=c.status,
            content_version=c.content_version,
            course_code=course.code,
            course_name=course.name,
            role=role,
        )
        for c, course, role in rows
    ]


def class_detail(db: Session, user: User, classroom: Class) -> ClassDetail:
    course = db.get(Course, classroom.course_id)
    assert course is not None
    role = class_role(db, user, classroom.id)
    assert role is not None  # require_class_member has already checked access.
    query = select(Lesson).where(Lesson.class_id == classroom.id)
    if role == "student":
        query = query.where(Lesson.is_published.is_(True))
    lessons = db.scalars(query.order_by(Lesson.position, Lesson.created_at, Lesson.id))
    return ClassDetail(
        id=classroom.id,
        course_id=classroom.course_id,
        code=classroom.code,
        term=classroom.term,
        status=classroom.status,
        content_version=classroom.content_version,
        course_code=course.code,
        course_name=course.name,
        role=role,
        lessons=[LessonView.model_validate(lesson) for lesson in lessons],
    )


def create_lesson(db: Session, actor: User, classroom: Class, data: LessonCreate) -> Lesson:
    # Serialize automatic positions for concurrent creates in the same class.
    db.scalar(select(Class).where(Class.id == classroom.id).with_for_update())
    position = data.position
    if "position" not in data.model_fields_set:
        maximum = db.scalar(
            select(func.max(Lesson.position)).where(Lesson.class_id == classroom.id)
        )
        position = 0 if maximum is None else maximum + 1
    lesson = Lesson(class_id=classroom.id, title=data.title, position=position, is_published=False)
    db.add(lesson)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="lesson.create",
            target_type="lesson",
            target_id=lesson.id,
            detail={"title": lesson.title, "position": position, "is_published": False},
        )
    )
    db.commit()
    db.refresh(lesson)
    return lesson


def update_lesson(db: Session, actor: User, lesson: Lesson, data: LessonUpdate) -> Lesson:
    changes = {
        key: value
        for key, value in data.model_dump(exclude_unset=True).items()
        if getattr(lesson, key) != value
    }
    for key, value in changes.items():
        setattr(lesson, key, value)
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="lesson.update",
            target_type="lesson",
            target_id=lesson.id,
            detail=changes,
        )
    )
    db.commit()
    db.refresh(lesson)
    return lesson
