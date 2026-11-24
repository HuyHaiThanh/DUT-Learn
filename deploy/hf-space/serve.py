"""Hosted-demo entry point: the unchanged API plus the built web app on one origin.

Same origin keeps the session cookie first-party, so no CORS settings are needed.
"""

import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.main import app

WEB = Path(os.environ.get("DUT_WEB_DIR", "/app/web")).resolve()

# No interactive API docs on the public demo.
app.router.routes = [
    route
    for route in app.router.routes
    if getattr(route, "path", None) not in {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
]
app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    if path == "api" or path.startswith("api/"):
        raise HTTPException(status_code=404)
    candidate = (WEB / path).resolve()
    if path and candidate.is_file() and candidate.is_relative_to(WEB):
        return FileResponse(candidate)
    return FileResponse(WEB / "index.html")
