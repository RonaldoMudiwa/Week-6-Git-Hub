"""Expense REST API.

A web API for recording and reporting on spending, built with FastAPI.

    from expense_api import ExpenseService, InMemoryRepository
"""

from .exceptions import ExpenseError, ExpenseNotFoundError, ValidationError
from .models import MAX_AMOUNT, Category, Expense, to_money
from .repository import ExpenseRepository, InMemoryRepository
from .service import ExpenseService

__version__ = "0.1.0"

__all__ = [
    "ExpenseService",
    "ExpenseRepository",
    "InMemoryRepository",
    "Expense",
    "Category",
    "to_money",
    "MAX_AMOUNT",
    "ExpenseError",
    "ExpenseNotFoundError",
    "ValidationError",
    "__version__",
]
