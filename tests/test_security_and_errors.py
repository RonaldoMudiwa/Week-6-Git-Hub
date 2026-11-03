"""Tests for API keys and the shape of every error."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from expense_api import ApiKeyChecker, ExpenseService, InMemoryRepository, Settings
from expense_api.app import create_app

KEYS = ("key-one", "key-two")
LUNCH = {"title": "Lunch", "amount": "8.50", "category": "food", "spent_on": "2026-10-28"}


@pytest.fixture
def locked(clock) -> TestClient:
    return TestClient(create_app(ExpenseService(InMemoryRepository(), clock), api_keys=KEYS))


def shape(body: dict) -> set:
    return set(body)


# ----------------------------------------------------------------------
# API keys
# ----------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/expenses", "/reports/summary", "/budgets", "/reports/budgets"])
def test_every_route_needs_a_key(locked, url):
    response = locked.get(url)
    assert response.status_code == 401
    assert response.json() == {"detail": "A valid API key is needed in the X-API-Key header.",
                               "code": "unauthorized", "fields": []}
    assert response.headers["WWW-Authenticate"] == "ApiKey"


def test_wrong_key(locked):
    assert locked.get("/expenses", headers={"X-API-Key": "key-three"}).status_code == 401
    assert locked.get("/expenses", headers={"X-API-Key": ""}).status_code == 401


@pytest.mark.parametrize("key", KEYS)
def test_any_listed_key_works(locked, key):
    headers = {"X-API-Key": key}
    assert locked.post("/expenses", json=LUNCH, headers=headers).status_code == 201
    assert locked.get("/expenses", headers=headers).json()["total"] >= 1


def test_writes_are_blocked_without_a_key_too(locked):
    assert locked.post("/expenses", json=LUNCH).status_code == 401
    assert locked.get("/expenses", headers={"X-API-Key": "key-one"}).json()["total"] == 0


def test_health_and_docs_stay_open(locked):
    assert locked.get("/health").json()["api_keys"] == "required"
    assert locked.get("/docs").status_code == 200
    assert locked.get("/openapi.json").status_code == 200


def test_docs_show_the_key_header(locked):
    schemes = locked.get("/openapi.json").json()["components"]["securitySchemes"]
    assert schemes["APIKeyHeader"] == {"type": "apiKey", "in": "header", "name": "X-API-Key"}


def test_checker():
    assert ApiKeyChecker().is_valid(None)                  # no keys set: open
    assert ApiKeyChecker(["", "  "]).enabled is False      # blank keys don't count
    checker = ApiKeyChecker([" secret "])
    assert checker.is_valid("secret")
    assert not checker.is_valid("secre")
    assert not checker.is_valid(None)


def test_keys_from_settings():
    assert Settings.from_env({"EXPENSE_API_KEYS": " a , b,, "}).api_keys == ("a", "b")
    assert Settings.from_env({}).api_keys == ()


# ----------------------------------------------------------------------
# Every error has the same shape
# ----------------------------------------------------------------------

@pytest.fixture
def client(clock) -> TestClient:
    # raise_server_exceptions=False lets us see what a user would see when
    # the app crashes, instead of the test itself crashing.
    return TestClient(create_app(ExpenseService(InMemoryRepository(), clock)),
                      raise_server_exceptions=False)


def test_pydantic_errors_are_reshaped(client):
    body = client.post("/expenses", json={"title": "", "amount": "-1", "colour": "red"}).json()
    assert body["code"] == "invalid"
    assert body["detail"] == "Please check: title, amount, colour."
    assert {f["field"] for f in body["fields"]} == {"title", "amount", "colour"}
    assert all(f["message"] for f in body["fields"])


def test_query_errors_name_the_parameter(client):
    body = client.get("/expenses?limit=500").json()
    assert body["fields"][0]["field"] == "limit"


def test_unknown_url(client):
    response = client.get("/nothing-here")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "not_found", "fields": []}


def test_wrong_method(client):
    response = client.patch("/expenses")
    assert response.status_code == 405
    assert response.json()["code"] == "http_error"


def test_a_crash_never_shows_the_inside_of_the_app(client, monkeypatch, caplog):
    service = client.app.state.service

    def broken():
        raise RuntimeError("database password is hunter2")

    monkeypatch.setattr(service, "list", broken)
    monkeypatch.setattr(service, "search", lambda query=None: broken())
    response = client.get("/expenses")

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side. Please try again.",
                               "code": "server_error", "fields": []}
    assert "hunter2" not in response.text
    assert "hunter2" in caplog.text           # but we can still find it in the log


@pytest.mark.parametrize("request_args", [
    ("get", "/expenses/99", None),
    ("post", "/expenses", {}),
    ("get", "/expenses?min_amount=9&max_amount=1", None),
    ("delete", "/budgets/food", None),
])
def test_every_error_has_the_same_three_keys(client, request_args):
    method, url, body = request_args
    response = client.request(method, url, json=body)
    assert response.status_code >= 400
    assert shape(response.json()) == {"detail", "code", "fields"}
