import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.constants import PROBLEM_MEDIA_TYPE, REQUEST_ID_HEADER

logger = logging.getLogger(__name__)


def problem_response(
    request: Request,
    status: HTTPStatus,
    code: str,
    detail: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = request.state.request_id
    return JSONResponse(
        {
            "type": "about:blank",
            "title": status.phrase,
            "status": status.value,
            "detail": detail,
            "instance": request.url.path,
            "code": code,
            "request_id": request_id,
        },
        status_code=status.value,
        media_type=PROBLEM_MEDIA_TYPE,
        headers={**(headers or {}), REQUEST_ID_HEADER: request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return problem_response(
            request,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "request_validation_failed",
            "One or more request fields are invalid.",
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
        status = HTTPStatus(error.status_code)
        code = (
            "request_too_large" if status is HTTPStatus.CONTENT_TOO_LARGE else status.name.lower()
        )
        return problem_response(request, status, code, status.description, error.headers)

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
            "The server could not complete the request.",
        )
