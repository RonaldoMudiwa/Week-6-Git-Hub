"""Whole program tests: the app built exactly the way main.py builds it,
with a real database file and API keys, used the way a person would."""

from __future__ import annotations

import importlib
from datetime import date

import pytest
from fastapi.testclient import TestClient

KEY = {"X-API-Key": "test-key"}


def start_app(monkeypatch, db_path) -> TestClient:
    """Start the app from settings, like running python -m expense_api."""
    monkeypatch.setenv("EXPENSE_DB", str(db_path))
    monkeypatch.setenv("EXPENSE_API_KEYS", "test-key")
    import expense_api.main

    main = importlib.reload(expense_api.main)
    return TestClient(main.app)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "expenses.db"


def test_a_month_of_spending(monkeypatch, db_path):
    client = start_app(monkeypatch, db_path)
    this_month = date.today().replace(day=1).isoformat()
    month = this_month[:7]

    # A key is needed for everything except /health.
    assert client.get("/health").json()["api_keys"] == "required"
    assert client.get("/expenses").status_code == 401

    for title, amount, category in [("Rent", "650", "rent"), ("Lunch", "8.50", "food"),
                                    ("Big shop", "64.10", "food"), ("Bus", "1.75", "transport")]:
        response = client.post("/expenses", headers=KEY, json={
            "title": title, "amount": amount, "category": category, "spent_on": this_month})
        assert response.status_code == 201

    # Fix a typo, then delete the bus fare.
    lunch_id = client.get("/expenses?search=lunch", headers=KEY).json()["items"][0]["id"]
    assert client.patch(f"/expenses/{lunch_id}", headers=KEY,
                        json={"amount": "9.50"}).json()["amount"] == "9.50"
    bus_id = client.get("/expenses?category=transport", headers=KEY).json()["items"][0]["id"]
    assert client.delete(f"/expenses/{bus_id}", headers=KEY).status_code == 204

    # Set a budget and see how it's going.
    client.put("/budgets/food", headers=KEY, json={"monthly_limit": "80"})
    food = client.get("/reports/budgets", headers=KEY).json()["budgets"][0]
    assert (food["spent"], food["state"]) == ("73.60", "close")

    summary = client.get(f"/reports/summary?date_from={this_month}", headers=KEY).json()
    assert summary["total"] == "723.60"
    assert summary["by_month"] == {month: "723.60"}


def test_everything_is_still_there_after_a_restart(monkeypatch, db_path):
    first = start_app(monkeypatch, db_path)
    first.post("/expenses", headers=KEY, json={"title": "Phone", "amount": "15", "category": "bills"})
    first.put("/budgets/bills", headers=KEY, json={"monthly_limit": "30"})

    again = start_app(monkeypatch, db_path)      # like closing the app and opening it again
    assert again.get("/expenses", headers=KEY).json()["items"][0]["title"] == "Phone"
    assert again.get("/budgets", headers=KEY).json() == [
        {"category": "bills", "monthly_limit": "30.00"}]
    # A new expense gets the next id, not one already used.
    new = again.post("/expenses", headers=KEY, json={"title": "Snack", "amount": "1"}).json()
    assert new["id"] == 2


def test_paging_through_everything(monkeypatch, db_path):
    client = start_app(monkeypatch, db_path)
    for n in range(1, 26):
        client.post("/expenses", headers=KEY, json={"title": f"Item {n}", "amount": n})

    seen, offset = [], 0
    while offset is not None:
        page = client.get(f"/expenses?limit=10&offset={offset}&sort=amount&order=asc",
                          headers=KEY).json()
        seen += [item["amount"] for item in page["items"]]
        offset = page["next_offset"]
    assert len(seen) == 25
    assert seen[0] == "1.00" and seen[-1] == "25.00"
