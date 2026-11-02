"""Reports: adding up spending in useful ways.

ReportService answers questions like "how much did I spend on food last
month?" and "am I over budget?". It only reads expenses, it never changes
them, so it's kept apart from ExpenseService.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Iterable

from .budgets import Budget, BudgetRepository, BudgetStatus
from .exceptions import ValidationError
from .models import Category, Expense
from .repository import ExpenseRepository

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class Summary:
    count: int = 0
    total: Decimal = ZERO
    average: Decimal = ZERO
    biggest: Expense | None = None
    by_category: dict[Category, Decimal] = field(default_factory=dict)
    by_month: dict[str, Decimal] = field(default_factory=dict)    # "2026-10" -> total


def summarise(expenses: Iterable[Expense]) -> Summary:
    """Totals by category and by month, the average and the biggest one."""
    expenses = list(expenses)
    if not expenses:
        return Summary()
    by_category: dict[Category, Decimal] = defaultdict(lambda: ZERO)
    by_month: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for expense in expenses:
        by_category[expense.category] += expense.amount
        by_month[expense.spent_on.strftime("%Y-%m")] += expense.amount
    total = sum((e.amount for e in expenses), ZERO)
    return Summary(
        count=len(expenses),
        total=total,
        average=(total / len(expenses)).quantize(Decimal("0.01")),
        biggest=max(expenses, key=lambda e: (e.amount, e.spent_on)),
        # Biggest category first. Months in date order.
        by_category=dict(sorted(by_category.items(), key=lambda item: (-item[1], item[0].value))),
        by_month=dict(sorted(by_month.items())),
    )


def month_range(month: str) -> tuple[date, date]:
    """"2026-11" -> (1 Nov 2026, 30 Nov 2026)."""
    try:
        first = date.fromisoformat(f"{month}-01")
    except (TypeError, ValueError):
        raise ValidationError(f"{month!r} isn't a month. Use YYYY-MM, like 2026-11.") from None
    next_month = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return first, date.fromordinal(next_month.toordinal() - 1)


class ReportService:
    def __init__(self, expenses: ExpenseRepository, budgets: BudgetRepository,
                 today: Callable[[], date] = date.today) -> None:
        self._expenses = expenses
        self._budgets = budgets
        self._today = today

    def summary(self, date_from: date | None = None, date_to: date | None = None) -> Summary:
        if date_from and date_to and date_from > date_to:
            raise ValidationError("date_from can't be after date_to.")
        chosen = [e for e in self._expenses.list()
                  if (date_from is None or e.spent_on >= date_from)
                  and (date_to is None or e.spent_on <= date_to)]
        return summarise(chosen)

    # Budgets ----------------------------------------------------------

    def set_budget(self, category: Category | str, monthly_limit) -> Budget:
        return self._budgets.save(Budget(category, monthly_limit))

    def budgets(self) -> list[Budget]:
        return self._budgets.all()

    def remove_budget(self, category: Category | str) -> bool:
        return self._budgets.remove(Category.parse(category))

    def this_month(self) -> str:
        return self._today().strftime("%Y-%m")

    def budget_report(self, month: str | None = None) -> list[BudgetStatus]:
        """How much of each budget is used in a month. This month if none given."""
        month = month or self.this_month()
        first, last = month_range(month)
        spent = self.summary(first, last).by_category
        return [BudgetStatus(b.category, b.monthly_limit, spent.get(b.category, ZERO))
                for b in self._budgets.all()]
