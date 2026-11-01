from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import SessionToken, User
from app.auth.security import token_hash
from app.courses.models import Class, ClassMember
from app.db import get_db

ClassRole = Literal["lecturer", "student"]


def get_current_session(request: Request, db: Session = Depends(get_db)) -> SessionToken:
    token = request.cookies.get("dut_session")
    if not token:
        raise HTTPException(401)
    session = db.scalar(
        select(SessionToken).where(
            SessionToken.token_hash == token_hash(token),
            SessionToken.expires_at > datetime.now(UTC),
            SessionToken.revoked_at.is_(None),
        )
    )
    if session is None:
        raise HTTPException(401)
    return session


def get_current_user(
    session: SessionToken = Depends(get_current_session), db: Session = Depends(get_db)
) -> User:
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401)
    return user


# Contract name retained for downstream modules.
require_user = get_current_user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.system_role != "admin":
        raise HTTPException(403)
    return user


def class_role(db: Session, user: User, class_id: UUID) -> ClassRole | None:
    role = db.scalar(
        select(ClassMember.role).where(
            ClassMember.class_id == class_id, ClassMember.user_id == user.id
        )
    )
    return role


def require_class_member(
    class_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Class:
    role = class_role(db, user, class_id)
    classroom = db.get(Class, class_id)
    if role is None or classroom is None or (role == "student" and classroom.status != "open"):
        raise HTTPException(404)
    return classroom


def require_class_lecturer(
    classroom: Class = Depends(require_class_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Class:
    if class_role(db, user, classroom.id) != "lecturer":
        raise HTTPException(403)
    return classroom
