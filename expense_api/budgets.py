"""Monthly budgets: how much you plan to spend on each category.

A budget is like putting £200 in an envelope marked "food" at the start of
the month. The budget report shows how much of each envelope is gone.
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from threading import Lock

from .exceptions import StorageError, ValidationError
from .models import MAX_AMOUNT, Category, to_money
from .sqlite_repository import MEMORY, from_pence, to_pence

WARN_AT = Decimal("80")   # percent used before a budget counts as "close"


@dataclass(frozen=True)
class Budget:
    category: Category
    monthly_limit: Decimal

    def __post_init__(self) -> None:
        limit = to_money(self.monthly_limit)
        if limit <= 0:
            raise ValidationError("A budget must be more than zero.")
        if limit > MAX_AMOUNT:
            raise ValidationError(f"A budget can't be more than {MAX_AMOUNT}.")
        object.__setattr__(self, "monthly_limit", limit)
        object.__setattr__(self, "category", Category.parse(self.category))


class BudgetState(str, Enum):
    OK = "ok"          # under 80% used
    CLOSE = "close"    # 80% or more used
    OVER = "over"      # more spent than planned


@dataclass(frozen=True)
class BudgetStatus:
    """One envelope at a point in the month."""

    category: Category
    monthly_limit: Decimal
    spent: Decimal

    @property
    def remaining(self) -> Decimal:
        # Negative when over budget, so you can see by how much.
        return self.monthly_limit - self.spent

    @property
    def percent_used(self) -> Decimal:
        return (self.spent / self.monthly_limit * 100).quantize(Decimal("0.1"))

    @property
    def state(self) -> BudgetState:
        if self.spent > self.monthly_limit:
            return BudgetState.OVER
        if self.percent_used >= WARN_AT:
            return BudgetState.CLOSE
        return BudgetState.OK


class BudgetRepository(ABC):
    """Where budgets are kept. One budget per category at most."""

    @abstractmethod
    def save(self, budget: Budget) -> Budget:
        """Add a budget, or replace the one already set for that category."""

    @abstractmethod
    def all(self) -> list[Budget]:
        """Every budget, in category order."""

    @abstractmethod
    def remove(self, category: Category) -> bool:
        """Remove a budget. False if there wasn't one."""


class InMemoryBudgetRepository(BudgetRepository):
    def __init__(self) -> None:
        self._budgets: dict[Category, Budget] = {}

    def save(self, budget: Budget) -> Budget:
        self._budgets[budget.category] = budget
        return budget

    def all(self) -> list[Budget]:
        return sorted(self._budgets.values(), key=lambda b: b.category.value)

    def remove(self, category: Category) -> bool:
        return self._budgets.pop(Category.parse(category), None) is not None


class SqliteBudgetRepository(BudgetRepository):
    """Budgets in their own table, in the same database file as the expenses."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS budgets (
        category    TEXT    PRIMARY KEY,
        limit_pence INTEGER NOT NULL CHECK (limit_pence > 0)
    );
    """

    def __init__(self, path: str | Path = MEMORY) -> None:
        try:
            if str(path) != MEMORY:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(path), check_same_thread=False)
            self._db.executescript(self.SCHEMA)
        except (sqlite3.Error, OSError) as error:
            raise StorageError(f"Could not open the database {path}: {error}") from error
        self._lock = Lock()

    def save(self, budget: Budget) -> Budget:
        with self._lock, self._db:
            # "Upsert": insert, or update the limit if the category already has one.
            self._db.execute(
                "INSERT INTO budgets (category, limit_pence) VALUES (?, ?) "
                "ON CONFLICT(category) DO UPDATE SET limit_pence = excluded.limit_pence",
                (budget.category.value, to_pence(budget.monthly_limit)))
        return budget

    def all(self) -> list[Budget]:
        with self._lock:
            rows = self._db.execute(
                "SELECT category, limit_pence FROM budgets ORDER BY category").fetchall()
        return [Budget(Category(category), from_pence(pence)) for category, pence in rows]

    def remove(self, category: Category) -> bool:
        with self._lock, self._db:
            cursor = self._db.execute("DELETE FROM budgets WHERE category = ?",
                                      (Category.parse(category).value,))
        return cursor.rowcount > 0

    def close(self) -> None:
        self._db.close()
