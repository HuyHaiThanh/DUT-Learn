from datetime import UTC, datetime, timedelta
from math import ceil
from secrets import token_urlsafe

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.models import LoginAttempt, SessionToken, User
from app.auth.schemas import MembershipView, MeView
from app.auth.security import token_hash, verify_password
from app.config import get_settings
from app.courses.models import Class, ClassMember, Course
from app.errors import APIError

MAX_FAILURES = 5
LOGIN_WINDOW = timedelta(minutes=15)


def me(db: Session, user: User) -> MeView:
    rows = db.execute(
        select(Class, Course, ClassMember.role)
        .join(Course, Course.id == Class.course_id)
        .join(ClassMember, ClassMember.class_id == Class.id)
        .where(ClassMember.user_id == user.id)
        .order_by(Class.code, Class.id)
    )
    return MeView(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        system_role=user.system_role,
        classes=[
            MembershipView(
                class_id=c.id,
                class_code=c.code,
                course_code=course.code,
                course_name=course.name,
                role=role,
            )
            for c, course, role in rows
        ],
    )


def login(db: Session, email: str, password: str, user_agent: str | None) -> tuple[User, str]:
    # Serialize attempts even for nonexistent accounts, across API processes.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 0))"), {"email": email})
    now = datetime.now(UTC)
    window_start = now - LOGIN_WINDOW
    failure_times = list(
        db.scalars(
            select(LoginAttempt.attempted_at)
            .where(
                LoginAttempt.email == email,
                LoginAttempt.succeeded.is_(False),
                LoginAttempt.attempted_at > window_start,
            )
            .order_by(LoginAttempt.attempted_at)
        )
    )
    failures = len(failure_times)
    if failures >= MAX_FAILURES:
        # The lock lifts once enough failures age out of the rolling window.
        unlock_at = failure_times[failures - MAX_FAILURES] + LOGIN_WINDOW
        retry_after = max(1, ceil((unlock_at - now).total_seconds()))
        raise APIError(
            429,
            "too_many_attempts",
            "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau.",
            {"retry_after_seconds": retry_after},
        )
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(password, user.password_hash if user else None)
    succeeded = valid and user is not None and user.is_active
    db.add(LoginAttempt(email=email, attempted_at=now, succeeded=succeeded))
    if not succeeded or user is None:
        # Failed attempts must persist even though the HTTP request is rejected.
        db.commit()
        raise APIError(
            401,
            "invalid_credentials",
            "Email hoặc mật khẩu không đúng.",
            {"attempts_remaining": MAX_FAILURES - failures - 1},
        )
    token = token_urlsafe(32)
    db.add(
        SessionToken(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
            user_agent=user_agent,
        )
    )
    db.commit()
    return user, token
