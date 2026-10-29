"""Shared test helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from expense_api import ExpenseService, InMemoryRepository


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


@pytest.fixture
def repository() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def service(repository, clock) -> ExpenseService:
    return ExpenseService(repository, clock)
