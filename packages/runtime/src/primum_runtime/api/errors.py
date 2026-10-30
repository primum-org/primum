"""Error responses: ``{"code", "params"}`` with an HTTP status chosen by code.

Every error the API returns has a code (decision 0009), including FastAPI's own: invalid bodies,
unknown paths and methods. Technical text never includes file paths or stack traces: from 1.4
the API is reachable from the local network.
"""

from collections.abc import Sequence

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from primum_runtime.api.models import ErrorBody
from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError

_STATUS_BY_CODE = {
    ErrorCode.OUTPUT_UNKNOWN: 404,
    ErrorCode.PANIC_ACTIVE: 409,
    ErrorCode.REQUEST_INVALID: 422,
    ErrorCode.REQUEST_NOT_FOUND: 404,
    ErrorCode.REQUEST_METHOD_NOT_ALLOWED: 405,
    ErrorCode.HAL_CLOSED: 503,
}
_DEFAULT_STATUS = 500
_CODE_BY_HTTP_STATUS = {
    404: ErrorCode.REQUEST_NOT_FOUND,
    405: ErrorCode.REQUEST_METHOD_NOT_ALLOWED,
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PrimumError)
    async def primum_error(_request: Request, error: PrimumError) -> JSONResponse:
        return error_response(error.code, dict(error.params))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, error: RequestValidationError) -> JSONResponse:
        problems = [(_location(item["loc"]), str(item["msg"])) for item in error.errors()]
        return error_response(
            ErrorCode.REQUEST_INVALID,
            {
                "fields": tuple(location for location, _ in problems),
                # Built from the problems only: str(error) names the endpoint's source file.
                "detail": "; ".join(f"{location}: {message}" for location, message in problems),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> Response:
        code = _CODE_BY_HTTP_STATUS.get(error.status_code)
        if code is None:
            return await http_exception_handler(request, error)
        return error_response(code, {"path": request.url.path})


def error_response(code: ErrorCode, params: dict[str, ErrorParam] | None = None) -> JSONResponse:
    body = ErrorBody(code=code.value, params=params or {})
    return JSONResponse(body.model_dump(), status_code=_STATUS_BY_CODE.get(code, _DEFAULT_STATUS))


def _location(parts: Sequence[object]) -> str:
    """``("body", "on")`` → ``"body.on"``."""
    return ".".join(map(str, parts))
