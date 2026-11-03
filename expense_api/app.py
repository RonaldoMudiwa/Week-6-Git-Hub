"""Building the FastAPI app.

create_app() puts the pieces together: the services, the endpoints, the
API key check and the error handlers. Tests call it with their own
services, so every test gets a fresh, empty app with a clock they control.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import Depends, FastAPI

from . import __version__
from .budgets import InMemoryBudgetRepository
from .errors import add_error_handlers
from .report_routes import router as report_router
from .reports import ReportService
from .repository import InMemoryRepository
from .routes import router
from .security import HEADER, ApiKeyChecker
from .service import ExpenseService

DESCRIPTION = f"""
Record what you spend and look it back up.

Amounts are sent and returned as text, like `"12.50"`, so no pennies are
ever lost to rounding.

If the server has API keys set, send one in the `{HEADER}` header. Every
error comes back as `{{"detail": ..., "code": ..., "fields": [...]}}`.
"""


def create_app(service: ExpenseService | None = None, reports: ReportService | None = None,
               api_keys: Iterable[str] = ()) -> FastAPI:
    app = FastAPI(title="Expense API", version=__version__, description=DESCRIPTION)
    service = service or ExpenseService(InMemoryRepository())
    app.state.service = service
    # Reports read the same expenses as the service, so the numbers always agree.
    app.state.reports = reports or ReportService(service.repository, InMemoryBudgetRepository(),
                                                 service.today)

    checker = ApiKeyChecker(api_keys)
    app.state.api_keys = checker
    # Every expense, report and budget route needs a key. /health and the
    # /docs page don't, so a server can check the app is alive without one.
    protected = [Depends(checker)]
    app.include_router(router, dependencies=protected)
    app.include_router(report_router, dependencies=protected)
    add_error_handlers(app)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """A quick "are you alive?" check, used by servers and monitoring."""
        return {"status": "ok", "version": __version__,
                "api_keys": "required" if checker.enabled else "off"}

    return app
