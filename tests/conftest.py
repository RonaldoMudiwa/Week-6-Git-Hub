"""Shared test helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from expense_api import ExpenseService, InMemoryRepository, SqliteRepository


class FakeClock:
    """A clock the tests control, so "today" is always the same day."""

    def __init__(self, start: datetime = datetime(2026, 10, 29, 12, 0)) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(params=["memory", "sqlite"])
def repository(request, tmp_path):
    """Every test that uses a repository runs twice, once for each kind.
    If both pass the same tests, they really can be swapped."""
    if request.param == "memory":
        yield InMemoryRepository()
    else:
        with SqliteRepository(tmp_path / "expenses.db") as repository:
            yield repository


@pytest.fixture
def service(repository, clock) -> ExpenseService:
    return ExpenseService(repository, clock)
