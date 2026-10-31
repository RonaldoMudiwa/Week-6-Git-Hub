"""All the errors this package can raise.

Everything inherits from ExpenseError, so one except clause catches the lot.
Later the API turns each one into the right HTTP status code.
"""

from __future__ import annotations


class ExpenseError(Exception):
    """Base class for every error in this package. Never raised directly."""


class ValidationError(ExpenseError):
    """A value isn't allowed, e.g. a negative amount."""


class ExpenseNotFoundError(ExpenseError):
    """No expense has that id."""

    def __init__(self, expense_id: int) -> None:
        self.expense_id = expense_id
        super().__init__(f"There's no expense with id {expense_id}.")


class StorageError(ExpenseError):
    """The database couldn't be opened, read or written."""
