"""The expense itself, before any web or database code gets involved.

Money is kept as Decimal, never float. A float can't hold 0.10 exactly, so
adding up lots of them slowly goes wrong, like a till that's a penny out by
the end of the day. Decimal counts in exact pennies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum, unique

from .exceptions import ValidationError

MAX_AMOUNT = Decimal("1000000.00")
MAX_TITLE = 100
MAX_NOTE = 500
PENNY = Decimal("0.01")


@unique
class Category(str, Enum):
    """The kinds of spending. Being a str means it turns into JSON as plain text."""

    FOOD = "food"
    TRANSPORT = "transport"
    BILLS = "bills"
    RENT = "rent"
    SHOPPING = "shopping"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    OTHER = "other"

    @classmethod
    def parse(cls, value: Category | str) -> Category:
        """Accepts "Food", " food " or Category.FOOD."""
        if isinstance(value, Category):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            choices = ", ".join(c.value for c in cls)
            raise ValidationError(f"Unknown category {value!r}. Choose from: {choices}.") from None


def to_money(value: Decimal | int | float | str) -> Decimal:
    """Turn a value into pounds and pence, e.g. "12.5" -> Decimal("12.50").

    Floats go through str() first, so 0.1 becomes exactly 0.10 and not
    0.1000000000000000055511151231257827.
    """
    if isinstance(value, bool):
        raise ValidationError("An amount must be a number, not True or False.")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValidationError(f"{value!r} isn't a valid amount.") from None
    if not amount.is_finite():
        raise ValidationError("An amount must be a real number.")
    return amount.quantize(PENNY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Expense:
    """One thing that was paid for.

    Frozen, so it can't be changed by accident. Changes go through
    with_changes(), which hands back a new, checked copy.
    id is None until the repository saves it and gives it a number.
    """

    title: str
    amount: Decimal
    category: Category
    spent_on: date
    note: str = ""
    id: int | None = None
    created_at: datetime | None = field(default=None, compare=False)
    updated_at: datetime | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        title = self.title.strip() if isinstance(self.title, str) else ""
        if not title:
            raise ValidationError("An expense needs a title.")
        if len(title) > MAX_TITLE:
            raise ValidationError(f"The title can be at most {MAX_TITLE} characters.")
        note = self.note.strip() if isinstance(self.note, str) else ""
        if len(note) > MAX_NOTE:
            raise ValidationError(f"The note can be at most {MAX_NOTE} characters.")

        amount = to_money(self.amount)
        if amount <= 0:
            raise ValidationError("The amount must be more than zero.")
        if amount > MAX_AMOUNT:
            raise ValidationError(f"The amount can't be more than {MAX_AMOUNT}.")

        if not isinstance(self.spent_on, date) or isinstance(self.spent_on, datetime):
            raise ValidationError("spent_on must be a date.")

        # The dataclass is frozen, so the cleaned values are set this way.
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "note", note)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "category", Category.parse(self.category))

    def with_changes(self, **changes) -> Expense:
        """A copy with some fields changed, checked again like a new one."""
        allowed = {"title", "amount", "category", "spent_on", "note", "updated_at"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"Can't change: {', '.join(sorted(unknown))}.")
        return replace(self, **changes)
