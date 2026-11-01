"""Idempotent development fixtures; run with python -m app.seed."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.security import hash_password
from app.config import get_settings
from app.courses.models import Class, ClassMember, Course
from app.db import SessionLocal

# These are synthetic development accounts, never real user data.
ACCOUNTS = [
    ("admin@dutlearn.local", "Quản trị viên", "admin"),
    ("gv1@dutlearn.local", "Giảng viên 1", "user"),
    ("gv2@dutlearn.local", "Giảng viên 2", "user"),
    *((f"sv{i}@dutlearn.local", f"Sinh viên {i}", "user") for i in range(1, 5)),
]


def seed(db: Session) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(54005)"))
    users: dict[str, User] = {}
    for email, name, role in ACCOUNTS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=name,
                system_role=role,
                password_hash=hash_password(get_settings().seed_password),
            )
            db.add(user)
            db.flush()
        users[email] = user
    course = db.scalar(select(Course).where(Course.code == "KTLT"))
    if course is None:
        course = Course(code="KTLT", name="Kỹ thuật lập trình")
        db.add(course)
        db.flush()
    for code, status, roster in [
        ("KTLT-01", "open", [("gv1", "lecturer"), ("sv1", "student"), ("sv2", "student")]),
        ("KTLT-02", "open", [("gv2", "lecturer"), ("sv3", "student"), ("sv4", "student")]),
        ("KTLT-CLOSED", "closed", [("gv1", "lecturer"), ("sv1", "student")]),
    ]:
        classroom = db.scalar(
            select(Class).where(
                Class.course_id == course.id, Class.code == code, Class.term == "2026-2027.1"
            )
        )
        if classroom is None:
            classroom = Class(course_id=course.id, code=code, term="2026-2027.1", status=status)
            db.add(classroom)
            db.flush()
        for account, role in roster:
            user = users[f"{account}@dutlearn.local"]
            member = db.scalar(
                select(ClassMember).where(
                    ClassMember.class_id == classroom.id, ClassMember.user_id == user.id
                )
            )
            if member is None:
                db.add(ClassMember(class_id=classroom.id, user_id=user.id, role=role))
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
    print("Development accounts seeded (existing accounts preserved).")
