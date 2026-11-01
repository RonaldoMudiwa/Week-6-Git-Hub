"""Searching, sorting and splitting expenses into pages.

ExpenseQuery is like the filters on a shopping website: pick a category,
a date range, a price range, type a word to search for, choose how to
sort, and see 20 results at a time instead of all 5,000 at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Callable, Iterable

from .exceptions import ValidationError
from .models import Category, Expense, to_money

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class SortField(str, Enum):
    DATE = "date"
    AMOUNT = "amount"
    TITLE = "title"
    CREATED = "created"


class Order(str, Enum):
    ASC = "asc"     # smallest, oldest or A first
    DESC = "desc"   # biggest, newest or Z first


@dataclass(frozen=True)
class ExpenseQuery:
    """What to look for. Every filter is optional, and leaving them all out
    means "everything, newest first, 20 at a time"."""

    category: Category | None = None
    date_from: date | None = None
    date_to: date | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    search: str | None = None
    sort: SortField = SortField.DATE
    order: Order = Order.DESC
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if self.category is not None:
            object.__setattr__(self, "category", Category.parse(self.category))
        for name in ("min_amount", "max_amount"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, to_money(value))
        search = (self.search or "").strip()
        object.__setattr__(self, "search", search or None)
        try:
            object.__setattr__(self, "sort", SortField(self.sort))
            object.__setattr__(self, "order", Order(self.order))
        except ValueError as error:
            raise ValidationError(str(error)) from None

        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError("date_from can't be after date_to.")
        if (self.min_amount is not None and self.max_amount is not None
                and self.min_amount > self.max_amount):
            raise ValidationError("min_amount can't be more than max_amount.")
        if not 1 <= self.limit <= MAX_LIMIT:
            raise ValidationError(f"limit must be between 1 and {MAX_LIMIT}.")
        if self.offset < 0:
            raise ValidationError("offset can't be negative.")

    def matches(self, expense: Expense) -> bool:
        """True if this expense passes every filter that's been set."""
        checks = [
            self.category is None or expense.category is self.category,
            self.date_from is None or expense.spent_on >= self.date_from,
            self.date_to is None or expense.spent_on <= self.date_to,
            self.min_amount is None or expense.amount >= self.min_amount,
            self.max_amount is None or expense.amount <= self.max_amount,
            self.search is None or self.search.lower() in
            f"{expense.title} {expense.note}".lower(),
        ]
        return all(checks)


@dataclass(frozen=True)
class Page:
    """One page of results, plus enough to know if there are more."""

    items: list[Expense] = field(default_factory=list)
    total: int = 0      # how many matched altogether, across every page
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    @property
    def next_offset(self) -> int | None:
        """Where the next page starts, or None if this is the last page."""
        following = self.offset + self.limit
        return following if following < self.total else None


# How each sort choice turns an expense into something Python can compare.
# The id comes second, so two expenses on the same day always come out in
# the same order.
_SORT_KEYS: dict[SortField, Callable[[Expense], tuple]] = {
    SortField.DATE: lambda e: (e.spent_on, e.id or 0),
    SortField.AMOUNT: lambda e: (e.amount, e.id or 0),
    SortField.TITLE: lambda e: (e.title.lower(), e.id or 0),
    SortField.CREATED: lambda e: (e.created_at or datetime.min, e.id or 0),
}


def run_query(expenses: Iterable[Expense], query: ExpenseQuery) -> Page:
    """Filter, sort and cut out one page, all in Python.

    Any repository can use this. A database can do the same job faster in
    SQL, so SqliteRepository has its own version.
    """
    matching = [e for e in expenses if query.matches(e)]
    matching.sort(key=_SORT_KEYS[query.sort], reverse=query.order is Order.DESC)
    page = matching[query.offset:query.offset + query.limit]
    return Page(page, len(matching), query.limit, query.offset)
