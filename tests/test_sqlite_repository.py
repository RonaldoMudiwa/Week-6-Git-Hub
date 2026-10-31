"""Tests only the SQLite repository needs: things a dictionary can't do,
like still being there after the program restarts."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal

import pytest

from expense_api import (
    Category,
    Expense,
    ExpenseService,
    InMemoryRepository,
    Settings,
    SqliteRepository,
    StorageError,
    build_repository,
)
from expense_api.sqlite_repository import from_pence, to_pence


def lunch(**overrides) -> Expense:
    values = dict(title="Lunch", amount="8.50", category=Category.FOOD,
                  spent_on=date(2026, 10, 31), note="with Sam",
                  created_at=datetime(2026, 10, 31, 12, 30), updated_at=datetime(2026, 10, 31, 12, 30))
    values.update(overrides)
    return Expense(**values)


def test_expenses_survive_a_restart(tmp_path):
    path = tmp_path / "expenses.db"
    with SqliteRepository(path) as repository:
        saved = repository.add(lunch())

    with SqliteRepository(path) as reopened:
        loaded = reopened.get(saved.id)

    assert loaded == saved
    assert loaded.note == "with Sam"
    assert loaded.created_at == datetime(2026, 10, 31, 12, 30)


def test_money_is_stored_as_whole_pennies(tmp_path):
    path = tmp_path / "expenses.db"
    with SqliteRepository(path) as repository:
        repository.add(lunch(amount="0.10"))
        repository.add(lunch(amount="1234.56"))

    rows = sqlite3.connect(path).execute("SELECT amount_pence FROM expenses ORDER BY id").fetchall()
    assert rows == [(10,), (123456,)]


@pytest.mark.parametrize("amount, pence", [
    (Decimal("8.50"), 850), (Decimal("0.01"), 1), (Decimal("1000000.00"), 100000000),
])
def test_pence_both_ways(amount, pence):
    assert to_pence(amount) == pence
    assert from_pence(pence) == amount
    assert str(from_pence(pence)) == str(amount)   # always 2 decimal places


def test_ids_are_never_reused_even_after_a_restart(tmp_path):
    path = tmp_path / "expenses.db"
    with SqliteRepository(path) as repository:
        repository.add(lunch())
        repository.add(lunch())
        repository.delete(2)
    with SqliteRepository(path) as repository:
        assert repository.add(lunch()).id == 3


def test_missing_timestamps_are_fine():
    with SqliteRepository() as repository:
        saved = repository.add(lunch(created_at=None, updated_at=None))
        assert repository.get(saved.id).created_at is None


def test_the_database_folder_is_made_if_needed(tmp_path):
    path = tmp_path / "new" / "folder" / "expenses.db"
    with SqliteRepository(path) as repository:
        assert repository.path == str(path)
    assert path.exists()


def test_a_file_that_isnt_a_database_gives_a_clear_error(tmp_path):
    path = tmp_path / "notes.db"
    path.write_text("this is not a database " * 100)
    with pytest.raises(StorageError, match="Could not open the database"):
        SqliteRepository(path)


def test_service_works_on_sqlite(tmp_path):
    with SqliteRepository(tmp_path / "expenses.db") as repository:
        service = ExpenseService(repository, lambda: datetime(2026, 10, 31, 9, 0))
        service.create("Bus", "1.75", "transport")
        service.create("Coffee", "3.20", "food")
        assert service.total() == Decimal("4.95")


# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------

def test_settings_default_to_a_file():
    settings = Settings.from_env({})
    assert settings.database == "data/expenses.db"
    assert not settings.in_memory


def test_settings_from_the_environment():
    assert Settings.from_env({"EXPENSE_DB": " other.db "}).database == "other.db"
    assert Settings.from_env({"EXPENSE_DB": "   "}).database == "data/expenses.db"
    assert Settings.from_env({"EXPENSE_DB": "MEMORY"}).in_memory


def test_settings_read_the_real_environment(monkeypatch):
    monkeypatch.setenv("EXPENSE_DB", "memory")
    assert Settings.from_env().in_memory


def test_build_repository(tmp_path):
    assert isinstance(build_repository(Settings("memory")), InMemoryRepository)
    repository = build_repository(Settings(str(tmp_path / "x.db")))
    assert isinstance(repository, SqliteRepository)
    repository.close()
