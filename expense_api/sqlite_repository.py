"""Keeping expenses in a SQLite database, so they're still there tomorrow.

SQLite is a whole database in one file. Python comes with it, so there's
nothing to install.

Money is saved as whole pennies (an integer), so £8.50 is stored as 850.
Databases can't be trusted to keep decimals exact, but whole numbers are
always exact. It's the same reason banks count in pennies.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock

from .exceptions import ExpenseNotFoundError, StorageError, ValidationError
from .models import Category, Expense
from .query import ExpenseQuery, Order, Page, SortField
from .repository import ExpenseRepository

MEMORY = ":memory:"

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    -- AUTOINCREMENT means a deleted id is never handed out again.
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    amount_pence INTEGER NOT NULL CHECK (amount_pence > 0),
    category     TEXT    NOT NULL,
    spent_on     TEXT    NOT NULL,
    note         TEXT    NOT NULL DEFAULT '',
    created_at   TEXT,
    updated_at   TEXT
);
CREATE INDEX IF NOT EXISTS expenses_by_date ON expenses (spent_on DESC, id DESC);
"""

COLUMNS = "id, title, amount_pence, category, spent_on, note, created_at, updated_at"

# Only these exact words can ever end up after ORDER BY. User input picks
# one of them, it's never pasted into the SQL itself.
SORT_COLUMNS = {
    SortField.DATE: "spent_on",
    SortField.AMOUNT: "amount_pence",
    SortField.TITLE: "title COLLATE NOCASE",
    SortField.CREATED: "created_at",
}


def to_pence(amount: Decimal) -> int:
    return int(amount * 100)


def from_pence(pence: int) -> Decimal:
    return (Decimal(pence) / 100).quantize(Decimal("0.01"))


class SqliteRepository(ExpenseRepository):
    """Expenses in a SQLite file, or in memory with ":memory:" for tests.

    The web server answers requests on several threads, so one connection is
    shared between them and a lock lets only one use it at a time, like one
    pen passed around a table.
    """

    def __init__(self, path: str | Path = MEMORY) -> None:
        self._path = str(path)
        try:
            if self._path != MEMORY:
                Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self._path, check_same_thread=False)
            self._db.executescript(SCHEMA)
        except (sqlite3.Error, OSError) as error:
            raise StorageError(f"Could not open the database {self._path}: {error}") from error
        self._lock = Lock()

    @property
    def path(self) -> str:
        return self._path

    def add(self, expense: Expense) -> Expense:
        if expense.id is not None:
            raise ValidationError("A new expense can't already have an id.")
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT INTO expenses (title, amount_pence, category, spent_on, note, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                self._values(expense))
        return replace(expense, id=cursor.lastrowid)

    def get(self, expense_id: int) -> Expense:
        with self._lock:
            row = self._db.execute(f"SELECT {COLUMNS} FROM expenses WHERE id = ?",
                                   (expense_id,)).fetchone()
        if row is None:
            raise ExpenseNotFoundError(expense_id)
        return self._to_expense(row)

    def list(self) -> list[Expense]:
        with self._lock:
            rows = self._db.execute(
                f"SELECT {COLUMNS} FROM expenses ORDER BY spent_on DESC, id DESC").fetchall()
        return [self._to_expense(row) for row in rows]

    def update(self, expense: Expense) -> Expense:
        with self._lock, self._db:
            cursor = self._db.execute(
                "UPDATE expenses SET title = ?, amount_pence = ?, category = ?, spent_on = ?, "
                "note = ?, created_at = ?, updated_at = ? WHERE id = ?",
                (*self._values(expense), expense.id))
        if cursor.rowcount == 0:
            raise ExpenseNotFoundError(expense.id)
        return expense

    def delete(self, expense_id: int) -> None:
        with self._lock, self._db:
            cursor = self._db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        if cursor.rowcount == 0:
            raise ExpenseNotFoundError(expense_id)

    def count(self) -> int:
        # Faster than loading every row just to count them.
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]

    def find(self, query: ExpenseQuery) -> Page:
        """The same answer as the base class gives, but the database does
        the filtering, sorting and counting, so only one page is loaded."""
        where, params = self._where(query)
        direction = "DESC" if query.order is Order.DESC else "ASC"
        order_by = f"{SORT_COLUMNS[query.sort]} {direction}, id {direction}"
        with self._lock:
            total = self._db.execute(f"SELECT COUNT(*) FROM expenses {where}", params).fetchone()[0]
            rows = self._db.execute(
                f"SELECT {COLUMNS} FROM expenses {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
                (*params, query.limit, query.offset)).fetchall()
        return Page([self._to_expense(row) for row in rows], total, query.limit, query.offset)

    @staticmethod
    def _where(query: ExpenseQuery) -> tuple[str, list]:
        """Build the WHERE part. Values always go in as ? placeholders, so
        typing SQL into the search box can't do any harm (SQL injection)."""
        conditions, params = [], []
        if query.category is not None:
            conditions.append("category = ?")
            params.append(query.category.value)
        if query.date_from is not None:
            conditions.append("spent_on >= ?")
            params.append(query.date_from.isoformat())
        if query.date_to is not None:
            conditions.append("spent_on <= ?")
            params.append(query.date_to.isoformat())
        if query.min_amount is not None:
            conditions.append("amount_pence >= ?")
            params.append(to_pence(query.min_amount))
        if query.max_amount is not None:
            conditions.append("amount_pence <= ?")
            params.append(to_pence(query.max_amount))
        if query.search is not None:
            # instr() looks for plain text, so % and _ in a search mean nothing special.
            conditions.append("instr(lower(title || ' ' || note), lower(?)) > 0")
            params.append(query.search)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return where, params

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> SqliteRepository:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Turning rows into expenses and back. Dates are saved as text like
    # "2026-10-31", which also sorts in the right order.

    @staticmethod
    def _values(expense: Expense) -> tuple:
        return (expense.title, to_pence(expense.amount), expense.category.value,
                expense.spent_on.isoformat(), expense.note,
                _text(expense.created_at), _text(expense.updated_at))

    @staticmethod
    def _to_expense(row: tuple) -> Expense:
        expense_id, title, pence, category, spent_on, note, created, updated = row
        return Expense(title, from_pence(pence), Category(category), date.fromisoformat(spent_on),
                       note, expense_id, _time(created), _time(updated))


def _text(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def _time(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None
