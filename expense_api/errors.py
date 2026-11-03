"""Every error the API sends has the same shape.

    {"detail": "There's no expense with id 42.", "code": "not_found", "fields": []}

A program using the API only has to learn one shape to handle any error,
like every shop using the same kind of receipt. "code" is a short word a
program can check, "detail" is a sentence for people, and "fields" says
which parts of the request were wrong when there are any.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import ExpenseError, ExpenseNotFoundError, ValidationError

log = logging.getLogger("expense_api")


class NotFoundError(ExpenseError):
    """Something other than an expense wasn't found, like a budget."""


class UnauthorizedError(ExpenseError):
    """No API key, or a wrong one."""


def error_body(detail: str, code: str, fields: list[dict] | None = None) -> dict:
    return {"detail": detail, "code": code, "fields": fields or []}


def _reply(status_code: int, detail: str, code: str, fields: list[dict] | None = None,
           headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(detail, code, fields),
                        headers=headers)


def _field_name(location: tuple) -> str:
    # Pydantic says where a problem is like ("body", "amount") or ("query", "limit").
    # The first part is just where in the request it came from.
    parts = [str(part) for part in location[1:]] or [str(part) for part in location]
    return ".".join(parts)


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ExpenseNotFoundError)
    @app.exception_handler(NotFoundError)
    def not_found(request: Request, error: ExpenseError) -> JSONResponse:
        return _reply(status.HTTP_404_NOT_FOUND, str(error), "not_found")

    @app.exception_handler(ValidationError)
    def invalid(request: Request, error: ValidationError) -> JSONResponse:
        return _reply(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error), "invalid")

    @app.exception_handler(UnauthorizedError)
    def unauthorized(request: Request, error: UnauthorizedError) -> JSONResponse:
        return _reply(status.HTTP_401_UNAUTHORIZED, str(error), "unauthorized",
                      headers={"WWW-Authenticate": "ApiKey"})

    @app.exception_handler(RequestValidationError)
    def bad_request(request: Request, error: RequestValidationError) -> JSONResponse:
        """Pydantic's own errors, turned into the same shape as ours."""
        fields = [{"field": _field_name(tuple(problem["loc"])), "message": problem["msg"]}
                  for problem in error.errors()]
        names = ", ".join(dict.fromkeys(f["field"] for f in fields))
        return _reply(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Please check: {names}.",
                      "invalid", fields)

    @app.exception_handler(StarletteHTTPException)
    def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        # Things like a URL that doesn't exist (404) or the wrong method (405).
        code = "not_found" if error.status_code == 404 else "http_error"
        return _reply(error.status_code, str(error.detail), code, headers=error.headers)

    @app.exception_handler(Exception)
    def crashed(request: Request, error: Exception) -> JSONResponse:
        """A bug. The details go in the log for us, never to the user, because
        they could show how the inside of the app works."""
        log.error("Unexpected error on %s %s", request.method, request.url.path, exc_info=error)
        return _reply(status.HTTP_500_INTERNAL_SERVER_ERROR,
                      "Something went wrong on our side. Please try again.", "server_error")
