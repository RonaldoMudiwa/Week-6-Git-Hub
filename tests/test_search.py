"""Tests for searching, sorting and pages.

Every test runs against both repositories (see conftest.py), so the fast
SQL version and the plain Python version must always give the same answer.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from expense_api import Category, ExpenseService, ValidationError
from expense_api.app import create_app
from expense_api.query import ExpenseQuery, Order, Page, SortField

# title, amount, category, day of October, note
SPENDING = [
    ("Rent", "650.00", "rent", 1, ""),
    ("Train to Brighton", "23.40", "transport", 3, "return ticket"),
    ("Lunch", "8.50", "food", 3, "with Sam"),
    ("big shop", "64.10", "food", 10, "Tesco"),
    ("Cinema", "12.00", "entertainment", 14, ""),
    ("Bus", "1.75", "transport", 20, ""),
    ("Coffee", "3.20", "food", 28, "100% arabica"),
    ("Phone bill", "15.00", "bills", 31, "under_score"),
]


@pytest.fixture
def filled(service, clock) -> ExpenseService:
    clock.now = datetime(2026, 11, 1, 12, 0)   # after every expense below
    for title, amount, category, day, note in SPENDING:
        service.create(title, amount, category, date(2026, 10, day), note)
        clock.advance(minutes=1)
    return service


def titles(page: Page) -> list[str]:
    return [e.title for e in page.items]


# ----------------------------------------------------------------------
# Filters
# ----------------------------------------------------------------------

def test_no_query_is_newest_first(filled):
    page = filled.search()
    assert titles(page)[:3] == ["Phone bill", "Coffee", "Bus"]
    assert page.total == 8


def test_category(filled):
    assert titles(filled.search(ExpenseQuery(category="food"))) == ["Coffee", "big shop", "Lunch"]


def test_date_range_includes_both_ends(filled):
    page = filled.search(ExpenseQuery(date_from=date(2026, 10, 3), date_to=date(2026, 10, 14)))
    assert titles(page) == ["Cinema", "big shop", "Lunch", "Train to Brighton"]


def test_amount_range_includes_both_ends(filled):
    page = filled.search(ExpenseQuery(min_amount="8.50", max_amount=23.4))
    assert titles(page) == ["Phone bill", "Cinema", "Lunch", "Train to Brighton"]


@pytest.mark.parametrize("words, expected", [
    ("lunch", ["Lunch"]),
    ("SAM", ["Lunch"]),                  # the note counts, and case doesn't matter
    ("  tesco ", ["big shop"]),
    ("100%", ["Coffee"]),                # % is just a character, not a wildcard
    ("_", ["Phone bill"]),               # same for _
    ("'; DROP TABLE expenses; --", []),  # SQL in the search box does nothing
])
def test_search(filled, words, expected):
    assert titles(filled.search(ExpenseQuery(search=words))) == expected
    assert filled.search().total == 8    # and the table is still there


def test_filters_combine(filled):
    page = filled.search(ExpenseQuery(category=Category.FOOD, min_amount=5, search="o"))
    assert titles(page) == ["big shop"]


def test_blank_search_means_no_search():
    assert ExpenseQuery(search="   ").search is None


# ----------------------------------------------------------------------
# Sorting
# ----------------------------------------------------------------------

@pytest.mark.parametrize("sort, order, first, last", [
    (SortField.DATE, Order.DESC, "Phone bill", "Rent"),
    (SortField.DATE, Order.ASC, "Rent", "Phone bill"),
    (SortField.AMOUNT, Order.DESC, "Rent", "Bus"),
    (SortField.AMOUNT, Order.ASC, "Bus", "Rent"),
    (SortField.TITLE, Order.ASC, "big shop", "Train to Brighton"),   # case doesn't matter
    (SortField.CREATED, Order.ASC, "Rent", "Phone bill"),
])
def test_sorting(filled, sort, order, first, last):
    page = filled.search(ExpenseQuery(sort=sort, order=order, limit=100))
    assert titles(page)[0] == first and titles(page)[-1] == last


def test_same_day_ties_always_come_out_the_same_way(filled):
    newest = titles(filled.search(ExpenseQuery(date_from=date(2026, 10, 3), date_to=date(2026, 10, 3))))
    oldest = titles(filled.search(ExpenseQuery(date_from=date(2026, 10, 3), date_to=date(2026, 10, 3),
                                               order="asc")))
    assert newest == ["Lunch", "Train to Brighton"]
    assert oldest == ["Train to Brighton", "Lunch"]


# ----------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------

def test_pages_cover_everything_once(filled):
    seen, offset = [], 0
    while offset is not None:
        page = filled.search(ExpenseQuery(limit=3, offset=offset))
        seen += titles(page)
        offset = page.next_offset
    assert len(seen) == 8 and len(set(seen)) == 8


def test_page_details(filled):
    page = filled.search(ExpenseQuery(limit=3, offset=6))
    assert (len(page.items), page.total, page.next_offset) == (2, 8, None)
    assert filled.search(ExpenseQuery(limit=3)).next_offset == 3


def test_offset_past_the_end_is_an_empty_page(filled):
    page = filled.search(ExpenseQuery(offset=50))
    assert page.items == [] and page.total == 8


# ----------------------------------------------------------------------
# Bad queries
# ----------------------------------------------------------------------

@pytest.mark.parametrize("values, message", [
    ({"date_from": date(2026, 10, 9), "date_to": date(2026, 10, 1)}, "date_from can't be after"),
    ({"min_amount": 10, "max_amount": 5}, "min_amount can't be more"),
    ({"limit": 0}, "limit must be between"),
    ({"limit": 101}, "limit must be between"),
    ({"offset": -1}, "offset can't be negative"),
    ({"sort": "colour"}, "colour"),
    ({"order": "sideways"}, "sideways"),
    ({"category": "sweets"}, "Unknown category"),
])
def test_bad_queries(values, message):
    with pytest.raises(ValidationError, match=message):
        ExpenseQuery(**values)


def test_query_cleans_its_values():
    query = ExpenseQuery(category="FOOD", min_amount="5", sort="amount", order="asc")
    assert query.category is Category.FOOD
    assert query.min_amount == Decimal("5.00")
    assert (query.sort, query.order) == (SortField.AMOUNT, Order.ASC)


# ----------------------------------------------------------------------
# Through the API
# ----------------------------------------------------------------------

@pytest.fixture
def client(filled) -> TestClient:
    return TestClient(create_app(filled))


def test_api_filters_and_pages(client):
    body = client.get("/expenses", params={"category": "food", "sort": "amount",
                                           "limit": 2}).json()
    assert [e["title"] for e in body["items"]] == ["big shop", "Lunch"]
    assert (body["total"], body["limit"], body["offset"], body["next_offset"]) == (3, 2, 0, 2)


def test_api_date_and_search(client):
    body = client.get("/expenses?date_from=2026-10-03&date_to=2026-10-03&search=sam").json()
    assert [e["title"] for e in body["items"]] == ["Lunch"]


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 500}, {"offset": -1}, {"sort": "colour"}, {"category": "sweets"},
    {"date_from": "yesterday"}, {"min_amount": -5}, {"search": "x" * 101},
])
def test_api_refuses_bad_parameters(client, params):
    assert client.get("/expenses", params=params).status_code == 422


def test_api_rules_from_the_query_class(client):
    response = client.get("/expenses?min_amount=10&max_amount=5")
    assert response.status_code == 422
    assert response.json() == {"detail": "min_amount can't be more than max_amount.",
                               "code": "invalid", "fields": []}


def test_created_sort_handles_missing_times(repository):
    from expense_api import Expense

    repository.add(Expense("Old", 1, "other", date(2026, 10, 1)))
    repository.add(Expense("New", 1, "other", date(2026, 10, 1), created_at=datetime(2026, 10, 2)))
    page = repository.find(ExpenseQuery(sort="created", order="asc"))
    assert [e.title for e in page.items] == ["Old", "New"]
