import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.admin.router import router as admin_router
from app.assignments.router import router as assignments_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.courses.router import router as courses_router
from app.db import get_db
from app.errors import error_response, http_error, validation_error
from app.ingest.worker import IngestWorker
from app.materials.router import router as materials_router
from app.practice.router import router as practice_router
from app.progress.router import router as progress_router
from app.rag.llm import register_llm_errors
from app.tutor.router import router as tutor_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    worker = IngestWorker() if os.environ.get("DUT_INGEST_WORKER", "1") != "0" else None
    if worker is not None:
        worker.start()
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


app = FastAPI(title="DUTLearn API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(HTTPException, http_error)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error)  # type: ignore[arg-type]
register_llm_errors(app)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(courses_router)
app.include_router(materials_router)
app.include_router(tutor_router)
app.include_router(progress_router)
app.include_router(practice_router)
app.include_router(assignments_router)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request.state.request_id = str(uuid4())
    try:
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.headers.get("X-DUT-CSRF") != "1"
        ):
            return error_response(request, 403, "csrf_required", "Thiếu xác nhận yêu cầu hợp lệ.")
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error: %s", request.state.request_id)
        response = error_response(request, 500, "internal_error", "Đã xảy ra lỗi máy chủ.")
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str | bool]:
    db_ok = False
    llm_ok = False
    try:
        db_ok = db.execute(text("SELECT 1")).scalar_one() == 1
    except SQLAlchemyError:
        db.rollback()
    settings = get_settings()
    base = settings.llm_base_url.rstrip("/")
    try:
        if settings.llm_provider == "openai":
            key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
            response = httpx.get(
                f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=2.0
            )
        else:
            response = httpx.get(f"{base}/api/version", timeout=2.0)
        llm_ok = response.is_success
    except httpx.HTTPError:
        pass
    return {"status": "ok", "db": db_ok, "llm": llm_ok}
