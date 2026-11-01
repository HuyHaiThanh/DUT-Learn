from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.models import SessionToken, User
from app.auth.schemas import LoginInput, MeView
from app.auth.service import login, me
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_session, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=MeView)
def login_route(
    payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)
) -> MeView:
    user, token = login(db, payload.email, payload.password, request.headers.get("user-agent"))
    settings = get_settings()
    response.set_cookie(
        "dut_session",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return me(db, user)


@router.get("/me", response_model=MeView)
def me_route(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeView:
    return me(db, user)


@router.post("/logout", status_code=204)
def logout_route(
    response: Response,
    user: User = Depends(get_current_user),
    session: SessionToken = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> None:
    session.revoked_at = datetime.now(UTC)
    db.commit()
    response.delete_cookie(
        "dut_session", path="/", httponly=True, samesite="lax", secure=get_settings().cookie_secure
    )
