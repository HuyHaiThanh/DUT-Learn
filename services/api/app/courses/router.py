from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.admin.schemas import ClassView
from app.auth.models import User
from app.courses.models import Class
from app.courses.schemas import MyClassView
from app.courses.service import my_classes
from app.db import get_db
from app.deps import get_current_user, require_class_member

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.get("", response_model=list[MyClassView])
def list_classes(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[MyClassView]:
    return my_classes(db, user)


@router.get("/{class_id}", response_model=ClassView)
def get_class(classroom: Class = Depends(require_class_member)) -> Class:
    return classroom
