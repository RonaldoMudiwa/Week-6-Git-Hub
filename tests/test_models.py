"""Tests for Expense, Category and money."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from expense_api import Category, Expense, ValidationError, to_money

DAY = date(2026, 10, 29)


def make(**overrides) -> Expense:
    values = {"title": "Lunch", "amount": "8.50", "category": Category.FOOD, "spent_on": DAY}
    values.update(overrides)
    return Expense(**values)


@pytest.mark.parametrize("value, money", [
    ("12.5", Decimal("12.50")), (3, Decimal("3.00")), (0.1, Decimal("0.10")),
    (" 4.99 ", Decimal("4.99")), ("2.675", Decimal("2.68")), (Decimal("1"), Decimal("1.00")),
])
def test_to_money(value, money):
    assert to_money(value) == money
    assert to_money(value).as_tuple().exponent == -2


def test_floats_add_up_exactly():
    # 0.1 + 0.2 is 0.30000000000000004 as a float, but not as money.
    assert to_money(0.1) + to_money(0.2) == Decimal("0.30")


@pytest.mark.parametrize("bad", ["abc", "", "NaN", "Infinity", True, None])
def test_to_money_refuses_bad_values(bad):
    with pytest.raises(ValidationError):
        to_money(bad)


def test_expense_cleans_its_values():
    expense = make(title="  Lunch  ", amount=8.5, category=" Food ", note=" with Sam ")
    assert expense.title == "Lunch"
    assert expense.amount == Decimal("8.50")
    assert expense.category is Category.FOOD
    assert expense.note == "with Sam"
    assert expense.id is None


@pytest.mark.parametrize("overrides, message", [
    ({"title": "   "}, "needs a title"),
    ({"title": None}, "needs a title"),
    ({"title": "x" * 101}, "at most 100"),
    ({"note": "x" * 501}, "at most 500"),
    ({"amount": 0}, "more than zero"),
    ({"amount": "-5"}, "more than zero"),
    ({"amount": "0.004"}, "more than zero"),       # rounds to 0.00
    ({"amount": "1000000.01"}, "can't be more than"),
    ({"spent_on": "2026-10-29"}, "must be a date"),
    ({"spent_on": datetime(2026, 10, 29, 9)}, "must be a date"),
    ({"category": "sweets"}, "Unknown category 'sweets'"),
])
def test_expense_refuses_bad_values(overrides, message):
    with pytest.raises(ValidationError, match=message):
        make(**overrides)


def test_a_note_of_none_becomes_empty():
    assert make(note=None).note == ""


def test_expense_is_frozen():
    with pytest.raises(AttributeError):
        make().amount = Decimal("1")  # type: ignore[misc]


def test_with_changes_gives_a_checked_copy():
    original = make()
    changed = original.with_changes(amount="9", title="Dinner")
    assert changed.amount == Decimal("9.00") and changed.title == "Dinner"
    assert original.amount == Decimal("8.50")   # the original is untouched
    with pytest.raises(ValidationError):
        original.with_changes(amount="-1")


def test_with_changes_refuses_unknown_fields():
    with pytest.raises(ValidationError, match="Can't change: colour, id"):
        make().with_changes(id=5, colour="red")


def test_timestamps_are_ignored_when_comparing():
    assert make(created_at=datetime(2026, 1, 1)) == make()


def test_category_parse():
    assert Category.parse(Category.RENT) is Category.RENT
    assert Category.parse("TRANSPORT") is Category.TRANSPORT
    assert Category.FOOD == "food"   # a str enum, so it's plain text in JSON
