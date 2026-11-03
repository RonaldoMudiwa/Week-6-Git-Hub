"""Tests for reports and budgets."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from expense_api import (
    Budget,
    BudgetState,
    BudgetStatus,
    Category,
    InMemoryBudgetRepository,
    ReportService,
    Settings,
    SqliteBudgetRepository,
    StorageError,
    ValidationError,
    build_budgets,
    summarise,
)
from expense_api.app import create_app
from expense_api.reports import month_range

# title, amount, category, date
SPENDING = [
    ("Rent", "650.00", "rent", date(2026, 10, 1)),
    ("Lunch", "8.50", "food", date(2026, 10, 3)),
    ("Big shop", "64.10", "food", date(2026, 10, 10)),
    ("Bus", "1.75", "transport", date(2026, 10, 20)),
    ("Coffee", "3.20", "food", date(2026, 11, 2)),
    ("Train", "23.40", "transport", date(2026, 11, 2)),
]


@pytest.fixture(params=["memory", "sqlite"])
def budgets(request, tmp_path):
    if request.param == "memory":
        yield InMemoryBudgetRepository()
    else:
        repository = SqliteBudgetRepository(tmp_path / "expenses.db")
        yield repository
        repository.close()


@pytest.fixture
def filled(service, clock):
    clock.now = datetime(2026, 11, 2, 18, 0)
    for title, amount, category, day in SPENDING:
        service.create(title, amount, category, day)
    return service


@pytest.fixture
def reports(filled, budgets) -> ReportService:
    return ReportService(filled.repository, budgets, filled.today)


# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------

def test_summary_of_everything(reports):
    summary = reports.summary()
    assert summary.count == 6
    assert summary.total == Decimal("750.95")
    assert summary.average == Decimal("125.16")
    assert summary.biggest.title == "Rent"


def test_categories_biggest_first_and_months_in_order(reports):
    summary = reports.summary()
    assert list(summary.by_category) == [Category.RENT, Category.FOOD, Category.TRANSPORT]
    assert summary.by_category[Category.FOOD] == Decimal("75.80")
    assert summary.by_month == {"2026-10": Decimal("724.35"), "2026-11": Decimal("26.60")}


def test_summary_for_a_date_range(reports):
    summary = reports.summary(date(2026, 10, 2), date(2026, 10, 31))
    assert summary.count == 3
    assert summary.total == Decimal("74.35")


def test_summary_of_nothing():
    summary = summarise([])
    assert (summary.count, summary.total, summary.biggest) == (0, Decimal("0.00"), None)


def test_summary_refuses_backwards_dates(reports):
    with pytest.raises(ValidationError):
        reports.summary(date(2026, 11, 1), date(2026, 10, 1))


@pytest.mark.parametrize("month, first, last", [
    ("2026-11", date(2026, 11, 1), date(2026, 11, 30)),
    ("2026-12", date(2026, 12, 1), date(2026, 12, 31)),     # year rolls over
    ("2028-02", date(2028, 2, 1), date(2028, 2, 29)),       # leap year
])
def test_month_range(month, first, last):
    assert month_range(month) == (first, last)


@pytest.mark.parametrize("bad", ["2026-13", "November", "", None])
def test_month_range_refuses_bad_months(bad):
    with pytest.raises(ValidationError, match="isn't a month"):
        month_range(bad)


# ----------------------------------------------------------------------
# Budgets
# ----------------------------------------------------------------------

def test_set_list_and_replace_budgets(reports):
    reports.set_budget("food", "200")
    reports.set_budget(Category.TRANSPORT, 50)
    reports.set_budget("food", "250")        # replaces, doesn't add a second one
    assert reports.budgets() == [Budget(Category.FOOD, Decimal("250.00")),
                                 Budget(Category.TRANSPORT, Decimal("50.00"))]


def test_remove_budget(reports):
    reports.set_budget("food", 200)
    assert reports.remove_budget("food") is True
    assert reports.remove_budget("food") is False
    assert reports.budgets() == []


@pytest.mark.parametrize("limit", [0, "-5", "1000000.01"])
def test_bad_budgets(limit):
    with pytest.raises(ValidationError):
        Budget("food", limit)


def test_budget_report_for_this_month(reports):
    reports.set_budget("food", "4.00")
    reports.set_budget("transport", "25.00")
    reports.set_budget("bills", "60.00")
    statuses = {s.category: s for s in reports.budget_report()}

    assert statuses[Category.BILLS].spent == Decimal("0.00")
    assert statuses[Category.BILLS].state is BudgetState.OK
    assert statuses[Category.FOOD].spent == Decimal("3.20")
    assert statuses[Category.FOOD].percent_used == Decimal("80.0")
    assert statuses[Category.FOOD].state is BudgetState.CLOSE
    assert statuses[Category.TRANSPORT].spent == Decimal("23.40")   # October's bus not counted


def test_budget_report_for_another_month(reports):
    reports.set_budget("food", "70")
    food = reports.budget_report("2026-10")[0]
    assert food.spent == Decimal("72.60")
    assert food.remaining == Decimal("-2.60")
    assert food.state is BudgetState.OVER


def test_budget_status_maths():
    status = BudgetStatus(Category.FOOD, Decimal("200.00"), Decimal("50.00"))
    assert (status.remaining, status.percent_used, status.state) == (
        Decimal("150.00"), Decimal("25.0"), BudgetState.OK)


def test_sqlite_budgets_survive_a_restart(tmp_path):
    path = tmp_path / "expenses.db"
    first = SqliteBudgetRepository(path)
    first.save(Budget("rent", "650"))
    first.close()
    again = SqliteBudgetRepository(path)
    assert again.all() == [Budget(Category.RENT, Decimal("650.00"))]
    again.close()


def test_sqlite_budgets_bad_file(tmp_path):
    path = tmp_path / "notes.db"
    path.write_text("not a database " * 100)
    with pytest.raises(StorageError):
        SqliteBudgetRepository(path)


def test_build_budgets(tmp_path):
    assert isinstance(build_budgets(Settings("memory")), InMemoryBudgetRepository)
    sqlite = build_budgets(Settings(str(tmp_path / "x.db")))
    assert isinstance(sqlite, SqliteBudgetRepository)
    sqlite.close()


# ----------------------------------------------------------------------
# Through the API
# ----------------------------------------------------------------------

@pytest.fixture
def client(filled) -> TestClient:
    return TestClient(create_app(filled))


def test_api_summary(client):
    body = client.get("/reports/summary").json()
    assert body["total"] == "750.95"
    assert body["biggest"]["title"] == "Rent"
    assert list(body["by_category"]) == ["rent", "food", "transport"]
    assert body["by_month"] == {"2026-10": "724.35", "2026-11": "26.60"}


def test_api_summary_with_dates(client):
    body = client.get("/reports/summary?date_from=2026-11-01").json()
    assert (body["count"], body["total"]) == (2, "26.60")


def test_api_summary_when_empty(clock):
    from expense_api import ExpenseService, InMemoryRepository

    body = TestClient(create_app(ExpenseService(InMemoryRepository(), clock))).get(
        "/reports/summary").json()
    assert body == {"count": 0, "total": "0.00", "average": "0.00", "biggest": None,
                    "by_category": {}, "by_month": {}}


def test_api_budgets(client):
    assert client.put("/budgets/food", json={"monthly_limit": "4"}).json() == {
        "category": "food", "monthly_limit": "4.00"}
    assert client.get("/budgets").json() == [{"category": "food", "monthly_limit": "4.00"}]

    report = client.get("/reports/budgets").json()
    assert report["month"] == "2026-11"
    assert report["budgets"][0] == {"category": "food", "monthly_limit": "4.00", "spent": "3.20",
                                    "remaining": "0.80", "percent_used": "80.0", "state": "close"}

    october = client.get("/reports/budgets?month=2026-10").json()
    assert october["budgets"][0]["state"] == "over"

    assert client.delete("/budgets/food").status_code == 204
    missing = client.delete("/budgets/food")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "There's no budget for food."


@pytest.mark.parametrize("method, url, body", [
    ("put", "/budgets/sweets", {"monthly_limit": "10"}),
    ("put", "/budgets/food", {"monthly_limit": "0"}),
    ("put", "/budgets/food", {"limit": "10"}),
    ("get", "/reports/budgets?month=November", None),
    ("get", "/reports/budgets?month=2026-13", None),
    ("get", "/reports/summary?date_from=2026-11-05&date_to=2026-11-01", None),
])
def test_api_refuses_bad_requests(client, method, url, body):
    response = client.request(method, url, json=body)
    assert response.status_code == 422


def test_sqlite_budgets_in_memory():
    repository = SqliteBudgetRepository()
    repository.save(Budget("food", 10))
    assert len(repository.all()) == 1
    repository.close()
