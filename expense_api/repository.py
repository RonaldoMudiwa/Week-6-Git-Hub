"""Where expenses are kept.

ExpenseRepository is the plug: it says what storage must be able to do,
not how. InMemoryRepository keeps everything in a dictionary, which is
perfect for tests. A SQLite version can be added later as another class,
and nothing that uses the repository has to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from threading import Lock

from .exceptions import ExpenseNotFoundError, ValidationError
from .models import Expense


class ExpenseRepository(ABC):
    @abstractmethod
    def add(self, expense: Expense) -> Expense:
        """Save a new expense and return it with its new id."""

    @abstractmethod
    def get(self, expense_id: int) -> Expense:
        """One expense. Raises ExpenseNotFoundError if there's no such id."""

    @abstractmethod
    def list(self) -> list[Expense]:
        """Every expense, newest spending first."""

    @abstractmethod
    def update(self, expense: Expense) -> Expense:
        """Replace a saved expense with a changed copy of it."""

    @abstractmethod
    def delete(self, expense_id: int) -> None:
        """Remove an expense. Raises ExpenseNotFoundError if there's no such id."""

    def count(self) -> int:
        return len(self.list())


def newest_first(expenses: list[Expense]) -> list[Expense]:
    """Latest date first. Same day? The one added last comes first."""
    return sorted(expenses, key=lambda e: (e.spent_on, e.id or 0), reverse=True)


class InMemoryRepository(ExpenseRepository):
    """Keeps expenses in a dictionary. Everything is lost when the program stops.

    A web server can handle two requests at the same moment, so a lock makes
    sure two new expenses can never be given the same id.
    """

    def __init__(self) -> None:
        self._expenses: dict[int, Expense] = {}
        self._next_id = 1
        self._lock = Lock()

    def add(self, expense: Expense) -> Expense:
        if expense.id is not None:
            raise ValidationError("A new expense can't already have an id.")
        with self._lock:
            saved = replace(expense, id=self._next_id)
            self._expenses[saved.id] = saved
            self._next_id += 1
        return saved

    def get(self, expense_id: int) -> Expense:
        try:
            return self._expenses[expense_id]
        except KeyError:
            raise ExpenseNotFoundError(expense_id) from None

    def list(self) -> list[Expense]:
        return newest_first(list(self._expenses.values()))

    def update(self, expense: Expense) -> Expense:
        if expense.id not in self._expenses:
            raise ExpenseNotFoundError(expense.id)
        with self._lock:
            self._expenses[expense.id] = expense
        return expense

    def delete(self, expense_id: int) -> None:
        with self._lock:
            if self._expenses.pop(expense_id, None) is None:
                raise ExpenseNotFoundError(expense_id)

    def count(self) -> int:
        return len(self._expenses)
