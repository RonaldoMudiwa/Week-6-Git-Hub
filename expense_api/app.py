"""Building the FastAPI app.

create_app() puts the pieces together: the service, the endpoints and the
error handlers. Tests call it with their own service, so every test gets a
fresh, empty app with a clock they control.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from . import __version__
from .budgets import InMemoryBudgetRepository
from .exceptions import ExpenseNotFoundError, ValidationError
from .report_routes import BudgetNotFoundError
from .report_routes import router as report_router
from .reports import ReportService
from .repository import InMemoryRepository
from .routes import router
from .service import ExpenseService

DESCRIPTION = """
Record what you spend and look it back up.

Amounts are sent and returned as text, like `"12.50"`, so no pennies are
ever lost to rounding.
"""


def create_app(service: ExpenseService | None = None,
               reports: ReportService | None = None) -> FastAPI:
    app = FastAPI(title="Expense API", version=__version__, description=DESCRIPTION)
    service = service or ExpenseService(InMemoryRepository())
    app.state.service = service
    # Reports read the same expenses as the service, so the numbers always agree.
    app.state.reports = reports or ReportService(service.repository, InMemoryBudgetRepository(),
                                                 service.today)
    app.include_router(router)
    app.include_router(report_router)

    # Our own errors become proper HTTP answers instead of a 500 crash.
    @app.exception_handler(BudgetNotFoundError)
    @app.exception_handler(ExpenseNotFoundError)
    def not_found(request: Request, error: ExpenseNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})

    @app.exception_handler(ValidationError)
    def invalid(request: Request, error: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            content={"detail": str(error)})

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """A quick "are you alive?" check, used by servers and monitoring."""
        return {"status": "ok", "version": __version__}

    return app
