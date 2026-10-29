"""Tests for the expense service."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from expense_api import Category, ExpenseNotFoundError, ExpenseService, InMemoryRepository, ValidationError


def test_create(service):
    expense = service.create("Train ticket", "23.40", "transport", date(2026, 10, 28), "to Brighton")
    assert expense.id == 1
    assert expense.amount == Decimal("23.40")
    assert expense.category is Category.TRANSPORT
    assert expense.created_at == expense.updated_at == datetime(2026, 10, 29, 12, 0)


def test_create_defaults_to_today_and_other(service):
    expense = service.create("Something", 5)
    assert expense.spent_on == date(2026, 10, 29)
    assert expense.category is Category.OTHER


def test_create_refuses_a_future_date(service):
    with pytest.raises(ValidationError, match="future"):
        service.create("Concert", 40, spent_on=date(2026, 10, 30))


def test_get_and_list(service):
    service.create("A", 1, spent_on=date(2026, 10, 1))
    service.create("B", 2, spent_on=date(2026, 10, 2))
    assert service.get(1).title == "A"
    assert [e.title for e in service.list()] == ["B", "A"]


def test_update_changes_only_what_is_given(service, clock):
    service.create("Lunch", "8.50", "food")
    clock.advance(hours=1)
    updated = service.update(1, amount="9.25", note=None)
    assert updated.amount == Decimal("9.25")
    assert updated.title == "Lunch" and updated.note == ""
    assert updated.updated_at == datetime(2026, 10, 29, 13, 0)
    assert updated.created_at == datetime(2026, 10, 29, 12, 0)
    assert service.get(1) == updated


def test_update_with_nothing_changes_nothing(service, clock):
    original = service.create("Lunch", 8)
    clock.advance(hours=1)
    assert service.update(1, title=None).updated_at == original.updated_at


def test_update_checks_the_new_values(service):
    service.create("Lunch", 8)
    with pytest.raises(ValidationError):
        service.update(1, amount=-3)
    with pytest.raises(ValidationError, match="future"):
        service.update(1, spent_on=date(2027, 1, 1))
    assert service.get(1).amount == Decimal("8.00")   # nothing was saved


@pytest.mark.parametrize("field", ["id", "created_at", "updated_at", "colour"])
def test_update_refuses_fields_the_user_cant_change(service, field):
    service.create("Lunch", 8)
    with pytest.raises(ValidationError, match="Can't change"):
        service.update(1, **{field: 1})


def test_update_missing(service):
    with pytest.raises(ExpenseNotFoundError):
        service.update(99, title="x")


def test_delete(service):
    service.create("Lunch", 8)
    service.delete(1)
    with pytest.raises(ExpenseNotFoundError):
        service.get(1)


def test_total_is_exact(service):
    assert service.total() == Decimal("0.00")
    for _ in range(10):
        service.create("Sweets", 0.1)
    assert service.total() == Decimal("1.00")


def test_default_clock_is_now():
    expense = ExpenseService(InMemoryRepository()).create("Lunch", 8)
    assert expense.spent_on == date.today()
