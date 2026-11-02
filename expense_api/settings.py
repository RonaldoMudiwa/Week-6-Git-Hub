"""Settings, read from environment variables.

Environment variables are settings given to a program from outside, so
the same code can use a test database on one computer and the real one on
another without being changed. Like a TV remote: same TV, different channel.

    EXPENSE_DB=data/expenses.db     where the database file lives (the default)
    EXPENSE_DB=memory               keep everything in memory, lost on restart
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from .budgets import BudgetRepository, InMemoryBudgetRepository, SqliteBudgetRepository
from .reports import ReportService
from .repository import ExpenseRepository, InMemoryRepository
from .service import ExpenseService
from .sqlite_repository import SqliteRepository

DEFAULT_DB = "data/expenses.db"


@dataclass(frozen=True)
class Settings:
    database: str = DEFAULT_DB

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(database=env.get("EXPENSE_DB", "").strip() or DEFAULT_DB)

    @property
    def in_memory(self) -> bool:
        return self.database.lower() == "memory"


def build_repository(settings: Settings) -> ExpenseRepository:
    if settings.in_memory:
        return InMemoryRepository()
    return SqliteRepository(settings.database)


def build_service(settings: Settings) -> ExpenseService:
    return ExpenseService(build_repository(settings))


def build_budgets(settings: Settings) -> BudgetRepository:
    if settings.in_memory:
        return InMemoryBudgetRepository()
    return SqliteBudgetRepository(settings.database)


def build_reports(settings: Settings, service: ExpenseService) -> ReportService:
    return ReportService(service.repository, build_budgets(settings), service.today)
