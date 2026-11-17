from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import require_user
from app.rag.llm import LLMClient, get_llm_client
from app.rag.retriever import Retriever, get_retriever
from app.tutor import service
from app.tutor.schemas import (
    AskRequest,
    AskResponse,
    CitationOpenResponse,
    MessageResponse,
    SessionResponse,
)

router = APIRouter(prefix="/api", tags=["tutor"])


def tutor_retriever(settings: Settings = Depends(get_settings)) -> Retriever:
    return get_retriever(settings)


@router.post("/tutor/ask", response_model=AskResponse)
def ask(
    data: AskRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
    retriever: Retriever = Depends(tutor_retriever),
) -> AskResponse:
    outcome = service.ask(
        db,
        user=user,
        data=data,
        retriever=retriever,
        llm=llm,
        settings=settings,
        request_id=request.state.request_id,
    )
    if outcome.error is not None:
        raise outcome.error
    assert outcome.response is not None
    return outcome.response


@router.get("/tutor/sessions", response_model=list[SessionResponse])
def sessions(
    class_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[SessionResponse]:
    return service.list_sessions(db, user, class_id)


@router.get("/tutor/sessions/{session_id}/messages", response_model=list[MessageResponse])
def messages(
    session_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[MessageResponse]:
    return service.list_messages(db, user, session_id)


@router.get("/citations/{citation_id}/open", response_model=CitationOpenResponse)
def citation(
    citation_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> CitationOpenResponse:
    return service.open_citation(db, user, citation_id)
