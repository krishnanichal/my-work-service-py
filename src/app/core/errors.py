import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.constants import PROBLEM_MEDIA_TYPE, PROBLEM_RESPONSE_HEADERS, REQUEST_ID_HEADER

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status: HTTPStatus, code: str, *, public_detail: str | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.public_detail = public_detail


def problem_response(
    request: Request,
    status: HTTPStatus,
    code: str,
    *,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, str | int] = {"message": status.phrase, "status": status.value, "code": code}
    if detail is not None:
        body["detail"] = detail
    response_headers = {REQUEST_ID_HEADER: request.state.request_id}
    if headers is not None:
        response_headers.update(
            (name, value)
            for name, value in headers.items()
            if name.lower() in PROBLEM_RESPONSE_HEADERS
        )
    return JSONResponse(
        body,
        status_code=status.value,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=response_headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return problem_response(request, error.status, error.code, detail=error.public_detail)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return problem_response(
            request,
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "request_validation_failed",
            detail="Check the request fields and parameter formats.",
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
        status = HTTPStatus(error.status_code)
        code = (
            "request_too_large" if status is HTTPStatus.CONTENT_TOO_LARGE else status.name.lower()
        )
        return problem_response(request, status, code, headers=error.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "Unhandled application exception",
            extra={"error_type": type(error).__name__, "request_id": request.state.request_id},
        )
        return problem_response(
            request,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "internal_server_error",
        )
