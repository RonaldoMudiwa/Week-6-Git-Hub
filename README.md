# Expense REST API

A web API for recording and reporting on spending, written in Python with
[FastAPI](https://fastapi.tiangolo.com). Other programs, like a website or a
phone app, will be able to add, change and look up expenses by sending it
HTTP requests.

Project 6 of a 12 week portfolio. Week 1 was an expense tracker for the
terminal. This week the same idea becomes a proper web API.

## Status

Day 3 of 7. The expense model, exact money handling, the service layer, a
FastAPI app with create, read, update and delete endpoints, and expenses
saved in a SQLite database so they're still there after a restart.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate           # macOS or Linux: source .venv/bin/activate
pip install -r requirements.txt

pytest                           # run the tests
python -m expense_api            # start the API on http://127.0.0.1:8000
```

Expenses are saved in `data/expenses.db`. To use another file, or keep
everything in memory, set `EXPENSE_DB` before starting:

```bash
set EXPENSE_DB=memory            # macOS or Linux: export EXPENSE_DB=memory
```

While it's running, open http://127.0.0.1:8000/docs. FastAPI builds that
page from the code, and every endpoint can be tried from there with a
"Try it out" button.

Needs Python 3.10 or newer.

## The endpoints

| Method | URL | Does | Answers |
| --- | --- | --- | --- |
| `POST` | `/expenses` | Add an expense | `201` and the new expense |
| `GET` | `/expenses` | List every expense, newest first | `200` |
| `GET` | `/expenses/{id}` | Get one | `200`, or `404` |
| `PUT` | `/expenses/{id}` | Replace all of it | `200`, or `404` |
| `PATCH` | `/expenses/{id}` | Change some fields | `200`, or `404` |
| `DELETE` | `/expenses/{id}` | Remove it | `204`, or `404` |
| `GET` | `/health` | Is the API up? | `200` |

```bash
curl -X POST http://127.0.0.1:8000/expenses \
     -H "Content-Type: application/json" \
     -d '{"title": "Lunch", "amount": "8.50", "category": "food"}'
```

```json
{
  "id": 1,
  "title": "Lunch",
  "amount": "8.50",
  "category": "food",
  "spent_on": "2026-10-30",
  "note": "",
  "created_at": "2026-10-30T12:00:00",
  "updated_at": "2026-10-30T12:00:00"
}
```

- **The right status codes.** `201 Created` with a `Location` header for a
  new expense, `204 No Content` after a delete, `404` for an id that doesn't
  exist and `422` for bad input. A program using the API can tell what
  happened just from the number.
- **Input is checked before our code runs.** The Pydantic models in
  `schemas.py` describe the JSON the API accepts. A missing title, an
  amount of `"abc"` or `1.005`, or an unknown category is sent back with a
  `422` that says exactly which field is wrong.
- **Typos are refused.** Sending `"ammount"` gets an error instead of being
  quietly ignored.
- **`PUT` vs `PATCH`.** `PUT` replaces the whole expense, like rewriting a
  receipt. `PATCH` changes only the fields that are sent, like correcting
  one number with a pen.
- **Amounts come back as text**, like `"8.50"`. JSON numbers are floats in
  many languages, and that would bring back the rounding problem.

## How it's built

```
routes.py  ->  ExpenseService  ->  ExpenseRepository  ->  storage
```

- **`routes.py`** has one short function per endpoint. It reads the
  request, asks the service to do the work and returns the answer. No rules
  live here.
- **`schemas.py`** holds the Pydantic models: the shape of the JSON going
  in and out. They're kept apart from `Expense`, so the API's JSON and the
  app's own model can each change without breaking the other.
- **`app.py`** builds the app with `create_app()`. It turns our own errors
  into proper `404` and `422` answers, so a missing expense never shows up
  as a crash. The tests call `create_app()` with their own service, so each
  test starts with an empty app and a clock it controls.
- **Dependency injection.** Each endpoint asks for the service with
  `Depends(get_service)` instead of creating one itself, like a worker
  being handed the tools for the job instead of bringing their own.
- **`Expense`** is one thing that was paid for: a title, an amount, a
  category, the date it was spent and an optional note. It's frozen, so it
  can't be changed by accident, and it checks its own values when it's made.
- **`ExpenseRepository`** is an abstract class that says what storage must
  do: add, get, list, update and delete. `InMemoryRepository` keeps
  everything in a dictionary, and `SqliteRepository` keeps it in a database
  file. Nothing above them can tell which one it has.
- **`ExpenseService`** holds the rules, like "no expenses dated in the
  future" and "you can't change an expense's id". It knows nothing about
  the web, so it's easy to test, like a kitchen that cooks the same food
  whether the order came from the counter or a delivery app.

```python
from expense_api import ExpenseService, InMemoryRepository

service = ExpenseService(InMemoryRepository())
lunch = service.create("Lunch", "8.50", "food")
service.update(lunch.id, amount="9.25")     # only the amount changes
service.total()                             # Decimal('9.25')
```

## Saving to SQLite

SQLite is a whole database in a single file, and it comes with Python, so
there's nothing extra to install.

- **Money is stored as whole pennies.** £8.50 is saved as `850`. Whole
  numbers are always exact in a database, decimals aren't always. Banks do
  the same.
- **Ids are never reused.** If expense 5 is deleted, the next one is 6, not
  5, even after a restart. Otherwise an old link to `/expenses/5` could
  quietly show someone a different expense.
- **One connection with a lock.** The web server can answer several
  requests at the same moment. A lock lets one request use the database at
  a time, like one pen being passed round a table.
- **Settings come from the environment.** `settings.py` reads `EXPENSE_DB`,
  so the same code can use a test database on one computer and the real one
  on another, without being changed.

**Same tests, both repositories.** Every repository, service and API test
runs twice, once with the in memory repository and once with SQLite. If
both pass the same tests, they really can be swapped. This is the
Liskov Substitution Principle: anything that says it's a repository has to
behave like one.

## Money

Amounts are kept as `Decimal`, never `float`. A float can't hold 0.10
exactly, so `0.1 + 0.2` gives `0.30000000000000004`. Add up a year of
spending like that and the total slowly drifts, like a till that's a penny
out by the end of the day. `Decimal` counts in exact pennies, and every
amount is rounded to 2 decimal places when it's made.

| Rule | Why |
| --- | --- |
| More than 0, at most 1,000,000 | Catches typos like a missing decimal point |
| Rounded to the penny | `2.675` becomes `2.68` |
| Not dated in the future | You can't have spent money tomorrow |
| Title up to 100 characters, note up to 500 | Keeps the data tidy |

## Categories

`food`, `transport`, `bills`, `rent`, `shopping`, `health`,
`entertainment`, `education`, `other`. Case and spaces don't matter, so
`" Food "` works too.

## Tests

```bash
pytest          # 161 tests
pytest --cov    # with a coverage report, fails below 95%
```

The API tests use FastAPI's `TestClient`. It sends real HTTP requests to
the app, but in memory, so no server has to be started.

## Week plan

| Day | Focus |
| --- | --- |
| 1 | Expense model, money, repository and service |
| 2 | FastAPI app with create, read, update and delete endpoints |
| 3 | Saving expenses in SQLite |
| 4 | Filtering, sorting and pages of results |
| 5 | Reports and monthly budgets |
| 6 | API keys and clearer error responses |
| 7 | Final tests and README |
