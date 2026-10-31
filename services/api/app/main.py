import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.db import get_db
from app.errors import error_response, http_error, validation_error

app = FastAPI(title="DUTLearn API", version="0.1.0")
app.add_exception_handler(HTTPException, http_error)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error)  # type: ignore[arg-type]
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
    try:
        response = httpx.get(f"{get_settings().llm_base_url.rstrip('/')}/api/version", timeout=2.0)
        llm_ok = response.is_success
    except httpx.HTTPError:
        pass
    return {"status": "ok", "db": db_ok, "llm": llm_ok}
