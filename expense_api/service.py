"""The rules of the app, kept apart from the web code.

ExpenseService is what the API will call. It doesn't know about HTTP or
JSON, so the same service could sit behind a website, a command line or a
phone app. It's like a kitchen: it cooks the same food whether the order
came from the counter, the phone or a delivery app.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from .exceptions import ValidationError
from .models import Category, Expense
from .query import ExpenseQuery, Page
from .repository import ExpenseRepository

Clock = Callable[[], datetime]

# The id and the timestamps are looked after by the app, never by the user.
EDITABLE = {"title", "amount", "category", "spent_on", "note"}


class ExpenseService:
    def __init__(self, repository: ExpenseRepository, clock: Clock | None = None) -> None:
        self._repository = repository
        self._clock = clock or datetime.now

    def create(self, title: str, amount: Decimal | str | int | float,
               category: Category | str = Category.OTHER, spent_on: date | None = None,
               note: str = "") -> Expense:
        """Record a new expense. No date means today."""
        now = self._clock()
        spent_on = spent_on or now.date()
        self._not_in_the_future(spent_on, now)
        expense = Expense(title, amount, category, spent_on, note,
                          created_at=now, updated_at=now)
        return self._repository.add(expense)

    def today(self) -> date:
        return self._clock().date()

    @property
    def repository(self) -> ExpenseRepository:
        """Read only access, so reports can share the same expenses."""
        return self._repository

    def get(self, expense_id: int) -> Expense:
        return self._repository.get(expense_id)

    def list(self) -> list[Expense]:
        return self._repository.list()

    def search(self, query: ExpenseQuery | None = None) -> Page:
        """One page of expenses matching the filters. No query means the
        newest 20."""
        return self._repository.find(query or ExpenseQuery())

    def update(self, expense_id: int, **changes: Any) -> Expense:
        """Change some fields of an expense. Fields left out stay the same.

        A change set to None is ignored, so a form that sends back empty
        fields doesn't wipe anything out by mistake.
        """
        changes = {name: value for name, value in changes.items() if value is not None}
        unknown = set(changes) - EDITABLE
        if unknown:
            raise ValidationError(f"Can't change: {', '.join(sorted(unknown))}.")
        current = self._repository.get(expense_id)
        if not changes:
            return current
        now = self._clock()
        if "spent_on" in changes:
            self._not_in_the_future(changes["spent_on"], now)
        return self._repository.update(current.with_changes(**changes, updated_at=now))

    def delete(self, expense_id: int) -> None:
        self._repository.delete(expense_id)

    def total(self) -> Decimal:
        """Everything spent, added up exactly."""
        return sum((e.amount for e in self._repository.list()), Decimal("0.00"))

    @staticmethod
    def _not_in_the_future(spent_on: Any, now: datetime) -> None:
        # You can't have spent money tomorrow.
        if isinstance(spent_on, date) and spent_on > now.date():
            raise ValidationError("An expense can't be dated in the future.")
