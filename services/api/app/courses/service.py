from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class, ClassMember, Course
from app.courses.schemas import MyClassView


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
