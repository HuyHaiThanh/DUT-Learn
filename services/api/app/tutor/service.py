import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings
from app.courses.models import Lesson
from app.deps import class_role, require_class_member
from app.errors import APIError
from app.materials.models import Chunk, Material, MaterialVersion
from app.materials.policy import can_read_version
from app.rag.llm import LLMClient, LLMError
from app.rag.retriever import RetrievalResult, Retriever
from app.rag.scope import versions_still_valid
from app.rag.threshold import passes_evidence_gate
from app.tutor.budget import fit_prompt
from app.tutor.citations import LIMITATION, parse_citations
from app.tutor.models import ChatMessage, ChatSession, Citation
from app.tutor.prompt import PROMPT_VERSION_ANSWER, PROMPT_VERSION_HINT
from app.tutor.schemas import (
    AskRequest,
    AskResponse,
    CitationOpenResponse,
    CitationResponse,
    MessageResponse,
    SessionResponse,
)

logger = logging.getLogger(__name__)
INSUFFICIENT = (
    "Học liệu của lớp chưa đủ căn cứ để trả lời câu hỏi này. "
    "Bạn có thể diễn đạt lại câu hỏi cụ thể hơn hoặc hỏi giảng viên."
)
WITHDRAWN = "Câu trả lời này dựa trên nguồn đã được thay thế hoặc thu hồi."


@dataclass
class AskOutcome:
    response: AskResponse | None
    retrieval: RetrievalResult
    timings_ms: dict[str, float]
    prompt_tokens_est: int
    prompt_eval_count: int | None
    error: APIError | LLMError | None = None


def require_open_class(db: Session, user: User, class_id: UUID) -> None:
    classroom = require_class_member(class_id, db, user)
    if classroom.status != "open":
        raise HTTPException(404)


def owned_session(db: Session, user: User, session_id: UUID) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(404)
    require_open_class(db, user, session.class_id)
    return session


def ask(
    db: Session,
    *,
    user: User,
    data: AskRequest,
    retriever: Retriever,
    llm: LLMClient,
    settings: Settings,
    request_id: str,
) -> AskOutcome:
    started = perf_counter()
    require_open_class(db, user, data.class_id)
    if data.lesson_id is not None:
        lesson = db.get(Lesson, data.lesson_id)
        if (
            lesson is None
            or lesson.class_id != data.class_id
            or (class_role(db, user, data.class_id) == "student" and not lesson.is_published)
        ):
            raise HTTPException(404)
    if data.material_id is not None:
        material = db.get(Material, data.material_id)
        version = (
            db.get(MaterialVersion, material.active_version_id)
            if material and material.active_version_id
            else None
        )
        if (
            material is None
            or material.class_id != data.class_id
            or version is None
            or not can_read_version(db, user, version)
        ):
            raise HTTPException(404)
    if data.session_id is not None:
        session = owned_session(db, user, data.session_id)
        if session.class_id != data.class_id:
            raise HTTPException(404)
    else:
        session = ChatSession(
            user_id=user.id,
            class_id=data.class_id,
            lesson_id=data.lesson_id,
            material_id=data.material_id,
        )
        db.add(session)
        db.flush()
    user_created = datetime.now(UTC)
    retrieved_at = perf_counter()
    retrieval = retriever.retrieve(
        db,
        user=user,
        class_id=data.class_id,
        query=data.question,
        k=settings.top_k,
        prefer_material_id=data.material_id,
        prefer_page_index=data.page_index,
    )
    timings = {"retrieve": (perf_counter() - retrieved_at) * 1000, "llm": 0.0, "total": 0.0}
    prompt_version = PROMPT_VERSION_HINT if data.mode == "hint" else PROMPT_VERSION_ANSWER
    answer = INSUFFICIENT
    status = "insufficient_evidence"
    error: APIError | LLMError | None = None
    tokens = 0
    prompt_eval_count = None
    ordinals: list[int] = []
    model = settings.llm_model
    limitation = None
    threshold = (
        settings.min_score_dense if retrieval.retriever == "dense" else settings.min_score_hybrid
    )
    if passes_evidence_gate(retrieval, threshold):
        try:
            retrieval, messages, tokens = fit_prompt(retrieval, data.question, data.mode, settings)
            llm_started = perf_counter()
            try:
                result = llm.generate(
                    messages, temperature=0, seed=42, max_tokens=settings.llm_max_tokens
                )
            finally:
                timings["llm"] = (perf_counter() - llm_started) * 1000
            model = result.model
            prompt_eval_count = result.prompt_tokens
            logger.info("tutor request_id=%s prompt_eval_count=%s", request_id, prompt_eval_count)
            used = [h for h in retrieval.hits if h.used_in_prompt]
            version_ids = {h.version_id for h in used}
            if (
                versions_still_valid(db, user=user, class_id=data.class_id, version_ids=version_ids)
                != version_ids
            ):
                raise APIError(
                    409,
                    "source_changed",
                    "Học liệu vừa được thay đổi hoặc thu hồi trong lúc trả lời. Hãy hỏi lại.",
                )
            if not result.text.lstrip().startswith("KHONG_DU_CAN_CU"):
                answer, ordinals = parse_citations(result.text, len(used))
                status = "ok"
                if not ordinals:
                    limitation = LIMITATION
        except (APIError, LLMError) as exc:
            error = exc
            status = "error"
    metadata = dict(
        session_id=session.id,
        mode=data.mode,
        retriever=retrieval.retriever,
        model=model,
        prompt_version=prompt_version,
        latency_ms=0,
        request_id=request_id,
    )
    user_message = ChatMessage(
        **metadata, role="user", content=data.question, status="ok", created_at=user_created
    )
    db.add(user_message)
    assistant = ChatMessage(
        **metadata,
        role="assistant",
        content=None if error else answer,
        status=status,
        error_code=error.code if error else None,
        created_at=datetime.now(UTC),
    )
    db.add(assistant)
    db.flush()
    citations: list[CitationResponse] = []
    used = [h for h in retrieval.hits if h.used_in_prompt]
    if error is None:
        for ordinal in ordinals:
            hit = used[ordinal - 1]
            citation = Citation(
                message_id=assistant.id,
                chunk_id=hit.chunk_id,
                version_id=hit.version_id,
                page_index=hit.page_index,
                excerpt=hit.text[:300],
                ordinal=ordinal,
            )
            db.add(citation)
            db.flush()
            citations.append(
                CitationResponse(
                    id=citation.id,
                    ordinal=ordinal,
                    material_id=hit.material_id,
                    material_title=hit.material_title,
                    version_id=hit.version_id,
                    page_index=hit.page_index,
                    page_label=hit.page_label,
                    excerpt=citation.excerpt,
                )
            )
    # Measure the full service path, including persistence work before the final commit.
    total = int((perf_counter() - started) * 1000)
    user_message.latency_ms = assistant.latency_ms = total
    response = (
        None
        if error
        else AskResponse(
            session_id=session.id,
            message_id=assistant.id,
            status="ok" if status == "ok" else "insufficient_evidence",
            answer=answer,
            citations=citations,
            limitation=limitation,
            retriever=retrieval.retriever,
            model=model,
            latency_ms=total,
            request_id=request_id,
        )
    )
    db.commit()
    timings["total"] = (perf_counter() - started) * 1000
    return AskOutcome(response, retrieval, timings, tokens, prompt_eval_count, error)


def list_sessions(db: Session, user: User, class_id: UUID) -> list[SessionResponse]:
    require_open_class(db, user, class_id)
    sessions = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id, ChatSession.class_id == class_id)
        .order_by(ChatSession.created_at.desc(), ChatSession.id)
    )
    response = []
    for session in sessions:
        messages = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            )
        )
        questions = [m.content for m in messages if m.role == "user" and m.content]
        response.append(
            SessionResponse(
                id=session.id,
                lesson_id=session.lesson_id,
                material_id=session.material_id,
                created_at=session.created_at,
                last_question=questions[-1][:120] if questions else None,
                message_count=len(messages),
            )
        )
    return response


def citation_response(db: Session, citation: Citation) -> CitationResponse:
    version = db.get(MaterialVersion, citation.version_id)
    assert version is not None
    material = db.get(Material, version.material_id)
    chunk = db.get(Chunk, citation.chunk_id)
    assert material is not None and chunk is not None
    return CitationResponse(
        id=citation.id,
        ordinal=citation.ordinal,
        material_id=material.id,
        material_title=material.title,
        version_id=citation.version_id,
        page_index=citation.page_index,
        page_label=chunk.page_label,
        excerpt=citation.excerpt,
    )


def list_messages(db: Session, user: User, session_id: UUID) -> list[MessageResponse]:
    session = owned_session(db, user, session_id)
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    response = []
    for message in messages:
        citations = list(
            db.scalars(
                select(Citation).where(Citation.message_id == message.id).order_by(Citation.ordinal)
            )
        )
        ids = {c.version_id for c in citations}
        withdrawn = (
            message.role == "assistant"
            and class_role(db, user, session.class_id) == "student"
            and versions_still_valid(db, user=user, class_id=session.class_id, version_ids=ids)
            != ids
        )
        response.append(
            MessageResponse(
                id=message.id,
                role=message.role,
                model=message.model if message.role == "assistant" else None,
                mode=message.mode,
                content=None if withdrawn else message.content,
                status="source_withdrawn" if withdrawn else message.status,
                error_code=message.error_code,
                created_at=message.created_at,
                citations=[] if withdrawn else [citation_response(db, c) for c in citations],
                notice=WITHDRAWN if withdrawn else None,
            )
        )
    return response


def open_citation(db: Session, user: User, citation_id: UUID) -> CitationOpenResponse:
    citation = db.get(Citation, citation_id)
    if citation is None:
        raise HTTPException(404)
    message = db.get(ChatMessage, citation.message_id)
    assert message is not None
    session = owned_session(db, user, message.session_id)
    ids = {citation.version_id}
    if versions_still_valid(db, user=user, class_id=session.class_id, version_ids=ids) != ids:
        raise APIError(410, "source_revoked", "Nguồn học liệu đã được thay thế hoặc thu hồi.")
    chunk = db.get(Chunk, citation.chunk_id)
    version = db.get(MaterialVersion, citation.version_id)
    assert chunk is not None and version is not None
    return CitationOpenResponse(
        version_id=version.id,
        material_id=version.material_id,
        page_index=citation.page_index,
        page_label=chunk.page_label,
        excerpt=citation.excerpt,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
    )
