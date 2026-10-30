"""Error responses: ``{"code", "params"}`` with an HTTP status chosen by code."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from primum_runtime.api.models import ErrorBody
from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError

_STATUS_BY_CODE = {
    ErrorCode.OUTPUT_UNKNOWN: 404,
    ErrorCode.PANIC_ACTIVE: 409,
    ErrorCode.REQUEST_INVALID: 422,
    ErrorCode.HAL_CLOSED: 503,
}
_DEFAULT_STATUS = 500


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PrimumError)
    async def primum_error(_request: Request, error: PrimumError) -> JSONResponse:
        return error_response(error.code, dict(error.params))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, error: RequestValidationError) -> JSONResponse:
        # pydantic's text is technical: it goes in `detail`, as system text does (decision 0009).
        fields = tuple(".".join(str(part) for part in item["loc"]) for item in error.errors())
        return error_response(ErrorCode.REQUEST_INVALID, {"fields": fields, "detail": str(error)})


def error_response(code: ErrorCode, params: dict[str, ErrorParam] | None = None) -> JSONResponse:
    body = ErrorBody(code=code.value, params=params or {})
    return JSONResponse(body.model_dump(), status_code=_STATUS_BY_CODE.get(code, _DEFAULT_STATUS))
