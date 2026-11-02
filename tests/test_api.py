"""Tests for the HTTP endpoints.

TestClient sends real HTTP requests to the app, but in memory, so no
server has to be started and nothing goes over the network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from expense_api import ExpenseService, InMemoryRepository, __version__
from expense_api.app import create_app

LUNCH = {"title": "Lunch", "amount": "8.50", "category": "food", "spent_on": "2026-10-28"}


@pytest.fixture
def client(repository, clock) -> TestClient:
    return TestClient(create_app(ExpenseService(repository, clock)))


def add(client: TestClient, **overrides) -> dict:
    response = client.post("/expenses", json={**LUNCH, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "version": __version__}


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------

def test_create(client):
    response = client.post("/expenses", json=LUNCH)
    body = response.json()
    assert response.status_code == 201
    assert response.headers["Location"] == "/expenses/1"
    assert body == {
        "id": 1, "title": "Lunch", "amount": "8.50", "category": "food",
        "spent_on": "2026-10-28", "note": "",
        "created_at": "2026-10-29T12:00:00", "updated_at": "2026-10-29T12:00:00",
    }


def test_create_with_only_the_required_fields(client):
    response = client.post("/expenses", json={"title": "Bus", "amount": 2})
    body = response.json()
    assert response.status_code == 201
    assert body["category"] == "other"
    assert body["spent_on"] == "2026-10-29"   # today, from the test clock
    assert body["amount"] == "2.00"


def test_amount_can_be_a_number_or_text(client):
    assert add(client, amount=12.5)["amount"] == "12.50"
    assert add(client, amount="0.1")["amount"] == "0.10"


@pytest.mark.parametrize("change, field", [
    ({"title": ""}, "title"),
    ({"title": "x" * 101}, "title"),
    ({"amount": 0}, "amount"),
    ({"amount": "-4"}, "amount"),
    ({"amount": "abc"}, "amount"),
    ({"amount": "1.005"}, "amount"),          # more than 2 decimal places
    ({"amount": "1000000.01"}, "amount"),
    ({"category": "sweets"}, "category"),
    ({"spent_on": "29/10/2026"}, "spent_on"),
    ({"ammount": "5"}, "ammount"),            # a typo is refused, not ignored
])
def test_create_refuses_bad_input(client, change, field):
    response = client.post("/expenses", json={**LUNCH, **change})
    assert response.status_code == 422
    assert field in str(response.json()["detail"])


def test_missing_fields(client):
    response = client.post("/expenses", json={})
    fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert response.status_code == 422
    assert fields == {"title", "amount"}


def test_future_date_is_refused_by_the_service(client):
    response = client.post("/expenses", json={**LUNCH, "spent_on": "2026-11-05"})
    assert response.status_code == 422
    assert response.json() == {"detail": "An expense can't be dated in the future."}


def test_titles_are_trimmed(client):
    assert add(client, title="  Lunch  ")["title"] == "Lunch"


# ----------------------------------------------------------------------
# Read
# ----------------------------------------------------------------------

def test_list_starts_empty(client):
    assert client.get("/expenses").json() == {
        "items": [], "total": 0, "limit": 20, "offset": 0, "next_offset": None}


def test_list_is_newest_first(client):
    add(client, title="Old", spent_on="2026-10-01")
    add(client, title="New", spent_on="2026-10-28")
    assert [e["title"] for e in client.get("/expenses").json()["items"]] == ["New", "Old"]


def test_get_one(client):
    add(client)
    response = client.get("/expenses/1")
    assert response.status_code == 200
    assert response.json()["title"] == "Lunch"


def test_get_missing(client):
    response = client.get("/expenses/42")
    assert response.status_code == 404
    assert response.json() == {"detail": "There's no expense with id 42."}


def test_id_must_be_a_number(client):
    assert client.get("/expenses/lunch").status_code == 422


# ----------------------------------------------------------------------
# Update
# ----------------------------------------------------------------------

def test_patch_changes_only_what_is_sent(client, clock):
    add(client, note="with Sam")
    clock.advance(hours=2)
    response = client.patch("/expenses/1", json={"amount": "9.25"})
    body = response.json()
    assert response.status_code == 200
    assert body["amount"] == "9.25"
    assert body["title"] == "Lunch" and body["note"] == "with Sam"
    assert body["updated_at"] == "2026-10-29T14:00:00"
    assert body["created_at"] == "2026-10-29T12:00:00"


def test_patch_with_an_empty_body_changes_nothing(client):
    before = add(client)
    assert client.patch("/expenses/1", json={}).json() == before


def test_patch_refuses_bad_values_and_unknown_fields(client):
    add(client)
    assert client.patch("/expenses/1", json={"amount": "-1"}).status_code == 422
    assert client.patch("/expenses/1", json={"id": 7}).status_code == 422
    assert client.get("/expenses/1").json()["amount"] == "8.50"


def test_patch_missing(client):
    assert client.patch("/expenses/9", json={"title": "x"}).status_code == 404


def test_put_replaces_every_field(client):
    add(client, note="with Sam")
    response = client.put("/expenses/1", json={"title": "Dinner", "amount": "20"})
    body = response.json()
    assert response.status_code == 200
    assert body["title"] == "Dinner" and body["amount"] == "20.00"
    assert body["note"] == ""                    # not sent, so back to its default
    assert body["category"] == "other"
    assert body["spent_on"] == "2026-10-29"


def test_put_needs_the_required_fields(client):
    add(client)
    assert client.put("/expenses/1", json={"title": "Dinner"}).status_code == 422


def test_put_missing(client):
    assert client.put("/expenses/3", json=LUNCH).status_code == 404


# ----------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------

def test_delete(client):
    add(client)
    response = client.delete("/expenses/1")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/expenses/1").status_code == 404


def test_delete_missing(client):
    assert client.delete("/expenses/1").status_code == 404


# ----------------------------------------------------------------------
# The app itself
# ----------------------------------------------------------------------

def test_docs_list_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {"/health", "/expenses", "/expenses/{expense_id}", "/reports/summary",
                          "/reports/budgets", "/budgets", "/budgets/{category}"}
    assert set(paths["/expenses/{expense_id}"]) == {"get", "put", "patch", "delete"}


def test_each_app_has_its_own_data(clock):
    first = TestClient(create_app(ExpenseService(InMemoryRepository(), clock)))
    second = TestClient(create_app(ExpenseService(InMemoryRepository(), clock)))
    add(first)
    assert second.get("/expenses").json()["total"] == 0


def test_main_app_uses_the_settings(monkeypatch, tmp_path):
    import importlib

    # Set first, so importing main never makes a real database file.
    monkeypatch.setenv("EXPENSE_DB", str(tmp_path / "main.db"))
    import expense_api.main

    main = importlib.reload(expense_api.main)
    assert TestClient(main.app).post("/expenses", json=LUNCH).status_code == 201
    assert (tmp_path / "main.db").exists()
