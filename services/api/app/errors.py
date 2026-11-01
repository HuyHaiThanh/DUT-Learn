from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class APIError(HTTPException):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(status_code=status)
        self.code = code
        self.message = message


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    request_id = request.state.request_id
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc, APIError):
        return error_response(request, exc.status_code, exc.code, exc.message)
    codes = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}
    messages = {
        404: "Không tìm thấy tài nguyên.",
        405: "Phương thức không được hỗ trợ.",
        401: "Vui lòng đăng nhập.",
        403: "Bạn không có quyền thực hiện thao tác này.",
    }
    response = error_response(
        request,
        exc.status_code,
        codes.get(exc.status_code, "http_error"),
        messages.get(exc.status_code, "Không thể thực hiện yêu cầu."),
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(request, 422, "validation_error", "Dữ liệu yêu cầu không hợp lệ.")
