"""What the API accepts and sends back, as Pydantic models.

These are the shapes of the JSON. FastAPI checks every request against
them before our code even runs, so a missing title or an amount of "abc"
gets a clear 422 error straight away. They also build the /docs page.

They're kept apart from Expense on purpose. Expense is how the app thinks
about spending, these are how the outside world talks to it. Either can
change without breaking the other.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import MAX_AMOUNT, MAX_NOTE, MAX_TITLE, Category, Expense


def amount_field(default=...):
    """The same amount rules everywhere. "..." means the field is required."""
    return Field(default, gt=0, le=MAX_AMOUNT, max_digits=9, decimal_places=2,
                 description="Pounds and pence, e.g. 12.50", examples=["12.50"])


class ExpenseIn(BaseModel):
    """A new expense, or a full replacement for one."""

    # Unknown fields are refused, so a typo like "ammount" isn't silently ignored.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=MAX_TITLE, examples=["Lunch"])
    amount: Decimal = amount_field()
    category: Category = Category.OTHER
    spent_on: date | None = Field(default=None, description="Leave out for today")
    note: str = Field(default="", max_length=MAX_NOTE)


class ExpenseChanges(BaseModel):
    """Some fields of an expense. Anything left out stays as it is."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE)
    amount: Decimal | None = amount_field(None)
    category: Category | None = None
    spent_on: date | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE)


class ExpenseOut(BaseModel):
    """An expense as the API sends it back."""

    id: int
    title: str
    amount: Decimal
    category: Category
    spent_on: date
    note: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, expense: Expense) -> ExpenseOut:
        return cls(id=expense.id, title=expense.title, amount=expense.amount,
                   category=expense.category, spent_on=expense.spent_on, note=expense.note,
                   created_at=expense.created_at, updated_at=expense.updated_at)


class ErrorOut(BaseModel):
    """Every error the API sends looks like this."""

    detail: str
