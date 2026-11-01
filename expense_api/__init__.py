"""Expense REST API.

A web API for recording and reporting on spending, built with FastAPI.

    from expense_api import ExpenseService, InMemoryRepository
"""

from .exceptions import ExpenseError, ExpenseNotFoundError, StorageError, ValidationError
from .models import MAX_AMOUNT, Category, Expense, to_money
from .query import ExpenseQuery, Order, Page, SortField
from .repository import ExpenseRepository, InMemoryRepository
from .service import ExpenseService
from .settings import Settings, build_repository, build_service
from .sqlite_repository import SqliteRepository

__version__ = "0.4.0"

__all__ = [
    "ExpenseService",
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
