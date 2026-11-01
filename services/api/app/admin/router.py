from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminUserView,
    ClassCreate,
    ClassView,
    CourseCreate,
    CourseView,
    MemberCreate,
    MemberView,
    UserCreate,
)
from app.admin.service import audit_deleted, save_created
from app.auth.models import User
from app.auth.security import hash_password
from app.courses.models import Class, ClassMember, Course
from app.db import get_db
from app.deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserView])
def users(db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)))


@router.post("/users", response_model=AdminUserView, status_code=201)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> User:
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        system_role=payload.system_role,
    )
    save_created(db, actor, user, "user")
    return user


@router.get("/courses", response_model=list[CourseView])
def courses(db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> list[Course]:
    return list(db.scalars(select(Course).order_by(Course.code)))


@router.post("/courses", response_model=CourseView, status_code=201)
def create_course(
    payload: CourseCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> Course:
    course = Course(**payload.model_dump())
    save_created(db, actor, course, "course")
    return course


@router.get("/classes", response_model=list[ClassView])
def classes(db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> list[Class]:
    return list(db.scalars(select(Class).order_by(Class.code, Class.id)))


@router.post("/classes", response_model=ClassView, status_code=201)
def create_class(
    payload: ClassCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> Class:
    if db.get(Course, payload.course_id) is None:
        raise HTTPException(404)
    classroom = Class(**payload.model_dump())
    save_created(db, actor, classroom, "class")
    return classroom


@router.get("/classes/{class_id}/members", response_model=list[MemberView])
def members(
    class_id: UUID, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> list[ClassMember]:
    if db.get(Class, class_id) is None:
        raise HTTPException(404)
    return list(
        db.scalars(
            select(ClassMember)
            .where(ClassMember.class_id == class_id)
            .order_by(ClassMember.user_id)
        )
    )


@router.post("/classes/{class_id}/members", response_model=MemberView, status_code=201)
def create_member(
    class_id: UUID,
    payload: MemberCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ClassMember:
    if db.get(Class, class_id) is None or db.get(User, payload.user_id) is None:
        raise HTTPException(404)
    member = ClassMember(class_id=class_id, **payload.model_dump())
    save_created(db, actor, member, "class_member")
    return member


@router.delete("/classes/{class_id}/members/{user_id}", status_code=204)
def delete_member(
    class_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> Response:
    member = db.scalar(
        select(ClassMember).where(ClassMember.class_id == class_id, ClassMember.user_id == user_id)
    )
    if member is None:
        raise HTTPException(404)
    audit_deleted(db, actor, member.id, "class_member")
    db.delete(member)
    db.commit()
    return Response(status_code=204)
