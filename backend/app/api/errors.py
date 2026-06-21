"""Problem Details (application/problem+json) helpers and exception handlers."""
from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.problem import FieldError, Problem

PROBLEM_MEDIA_TYPE = "application/problem+json"
CORRELATION_HEADER = "X-Correlation-ID"


class ProblemException(Exception):
    """Raise to emit a contract Problem response."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        field_errors: list[FieldError] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.field_errors = field_errors
        self.retry_after_seconds = retry_after_seconds
        super().__init__(detail)


def correlation_id(request: Request) -> str:
    return request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())


def _response(request: Request, problem: Problem) -> JSONResponse:
    headers = {CORRELATION_HEADER: problem.correlation_id}
    if problem.retry_after_seconds is not None:
        headers["Retry-After"] = str(problem.retry_after_seconds)
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def make_problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    field_errors: list[FieldError] | None = None,
    retry_after_seconds: int | None = None,
) -> Problem:
    return Problem(
        type=f"/problems/{code}",
        title=title,
        status=status,
        detail=detail,
        code=code,
        correlation_id=correlation_id(request),
        instance=request.url.path,
        field_errors=field_errors,
        retry_after_seconds=retry_after_seconds,
    )


async def problem_exception_handler(
    request: Request, exc: ProblemException
) -> JSONResponse:
    problem = make_problem(
        request,
        status=exc.status,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        field_errors=exc.field_errors,
        retry_after_seconds=exc.retry_after_seconds,
    )
    return _response(request, problem)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = [
        FieldError(
            field=".".join(str(p) for p in err.get("loc", []) if p != "body"),
            message=err.get("msg", "Invalid value"),
            code=err.get("type"),
        )
        for err in exc.errors()
    ]
    problem = make_problem(
        request,
        status=422,
        code="validation_error",
        title="Unprocessable Entity",
        detail="The request payload failed validation.",
        field_errors=field_errors,
    )
    return _response(request, problem)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    problem = make_problem(
        request,
        status=exc.status_code,
        code="http_error",
        title="HTTP Error",
        detail=str(exc.detail),
    )
    return _response(request, problem)


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    problem = make_problem(
        request,
        status=500,
        code="internal_error",
        title="Internal Server Error",
        detail="An unexpected error occurred.",
    )
    return _response(request, problem)
