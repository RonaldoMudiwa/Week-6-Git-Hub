"""Tests every repository must pass. conftest.py runs each one against
both the in memory and the SQLite repository."""

from __future__ import annotations

from datetime import date
from threading import Thread

import pytest

from expense_api import Category, Expense, ExpenseNotFoundError, ExpenseRepository, ValidationError


def expense(title="Lunch", day=date(2026, 10, 29), amount="5") -> Expense:
    return Expense(title, amount, Category.FOOD, day)


def test_it_is_a_repository(repository):
    assert isinstance(repository, ExpenseRepository)


def test_add_gives_ids_in_order(repository):
    first = repository.add(expense("A"))
    second = repository.add(expense("B"))
    assert (first.id, second.id) == (1, 2)
    assert repository.get(2) == second
    assert repository.count() == 2


def test_add_refuses_an_expense_that_already_has_an_id(repository):
    saved = repository.add(expense())
    with pytest.raises(ValidationError):
        repository.add(saved)


def test_get_missing(repository):
    with pytest.raises(ExpenseNotFoundError, match="no expense with id 7") as error:
        repository.get(7)
    assert error.value.expense_id == 7


def test_list_is_newest_first(repository):
    repository.add(expense("Old", date(2026, 10, 1)))
    repository.add(expense("New", date(2026, 10, 28)))
    repository.add(expense("Also new", date(2026, 10, 28)))
    assert [e.title for e in repository.list()] == ["Also new", "New", "Old"]


def test_update(repository):
    saved = repository.add(expense())
    repository.update(saved.with_changes(title="Brunch"))
    assert repository.get(saved.id).title == "Brunch"


def test_update_missing(repository):
    with pytest.raises(ExpenseNotFoundError):
        repository.update(expense())


def test_delete(repository):
    saved = repository.add(expense())
    repository.delete(saved.id)
    assert repository.count() == 0
    with pytest.raises(ExpenseNotFoundError):
        repository.delete(saved.id)


def test_deleted_ids_are_never_reused(repository):
    repository.add(expense())
    repository.delete(1)
    assert repository.add(expense()).id == 2


def test_ids_stay_unique_when_adding_at_the_same_time(repository):
    threads = [Thread(target=lambda: [repository.add(expense()) for _ in range(50)])
               for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    ids = [e.id for e in repository.list()]
    assert len(ids) == 400 and len(set(ids)) == 400


def test_base_class_count_uses_list():
    class ListOnly(ExpenseRepository):
        def add(self, expense): ...
        def get(self, expense_id): ...
        def list(self): return [expense(), expense()]
        def update(self, expense): ...
        def delete(self, expense_id): ...

    assert ListOnly().count() == 2
