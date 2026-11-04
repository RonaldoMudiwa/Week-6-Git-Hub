"""Expense REST API.

A web API for recording and reporting on spending, built with FastAPI.

    from expense_api import ExpenseService, InMemoryRepository
"""

from .budgets import (
    Budget,
    BudgetRepository,
    BudgetState,
    BudgetStatus,
    InMemoryBudgetRepository,
    SqliteBudgetRepository,
)
from .exceptions import ExpenseError, ExpenseNotFoundError, StorageError, ValidationError
from .models import MAX_AMOUNT, Category, Expense, to_money
from .query import ExpenseQuery, Order, Page, SortField
from .reports import ReportService, Summary, summarise
from .repository import ExpenseRepository, InMemoryRepository
from .security import ApiKeyChecker
from .service import ExpenseService
from .settings import Settings, build_budgets, build_reports, build_repository, build_service
from .sqlite_repository import SqliteRepository

__version__ = "1.0.0"

__all__ = [
    "ExpenseService",
    "ApiKeyChecker",
    "ReportService",
    "Summary",
    "summarise",
    "Budget",
    "BudgetStatus",
    "BudgetState",
    "BudgetRepository",
    "InMemoryBudgetRepository",
    "SqliteBudgetRepository",
    "build_budgets",
    "build_reports",
    "ExpenseRepository",
    "InMemoryRepository",
    "SqliteRepository",
    "Settings",
    "build_repository",
    "build_service",
    "Expense",
    "ExpenseQuery",
    "Page",
    "SortField",
    "Order",
    "Category",
    "to_money",
    "MAX_AMOUNT",
    "ExpenseError",
    "ExpenseNotFoundError",
    "ValidationError",
    "StorageError",
    "__version__",
]
