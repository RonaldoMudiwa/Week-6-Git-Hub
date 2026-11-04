# Expense REST API

A web API for recording and reporting on spending, written in Python with
[FastAPI](https://fastapi.tiangolo.com). Other programs, like a website or a
phone app, will be able to add, change and look up expenses by sending it
HTTP requests.

Project 6 of a 12 week portfolio. Week 1 was an expense tracker for the
terminal. This week the same idea becomes a proper web API.

## Status

Finished. A REST API for expenses with create, read, update and delete,
exact money handling, SQLite storage, searching, sorting and pages,
spending reports, monthly budgets, API keys and one shape for every error.
328 tests with 100% coverage, run against both in memory and SQLite
storage.

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

## API keys

An API key is a password for programs, like a membership card shown at the
door. Set one or more keys before starting the server and every request
must send one:

```bash
set EXPENSE_API_KEYS=my-long-secret-key,another-key
python -m expense_api
```

```bash
curl http://127.0.0.1:8000/expenses -H "X-API-Key: my-long-secret-key"
```

- With no keys set, nothing is needed. Handy for trying it on your own
  computer.
- `/health` and `/docs` never need a key, so a server can check the app is
  alive. `/health` says whether keys are `required` or `off`.
- Keys are compared with `hmac.compare_digest`, which takes the same time
  however much of a wrong key is right. A normal `==` stops at the first
  wrong letter, and an attacker could time the answers to guess a key one
  letter at a time.
- The check is a FastAPI dependency added to every router in one place, so
  a new endpoint can't forget it.
- On the docs page, click **Authorize** and paste a key to try the
  protected endpoints.

## Errors

Every error has the same three parts, whatever went wrong:

```json
{
  "detail": "Please check: amount.",
  "code": "invalid",
  "fields": [{"field": "amount", "message": "Input should be greater than 0"}]
}
```

| Code | Status | When |
| --- | --- | --- |
| `invalid` | 422 | Bad input: a wrong type, a rule broken, a typo in a field name |
| `not_found` | 404 | No expense or budget with that id, or a URL that doesn't exist |
| `unauthorized` | 401 | Missing or wrong API key |
| `http_error` | 405 and others | Like using `PATCH` where it isn't allowed |
| `server_error` | 500 | A bug on our side |

- A program only has to learn one shape to handle any error, like every
  shop using the same kind of receipt.
- Pydantic's own errors, which normally look different, are turned into
  this shape too.
- When something crashes, the real error goes in the server's log, and the
  user only sees a polite message. Error messages can leak secrets or show
  how the inside of an app works, and there's a test that checks they don't.

While it's running, open http://127.0.0.1:8000/docs. FastAPI builds that
page from the code, and every endpoint can be tried from there with a
"Try it out" button.

Needs Python 3.10 or newer.

## The endpoints

| Method | URL | Does | Answers |
| --- | --- | --- | --- |
| `POST` | `/expenses` | Add an expense | `201` and the new expense |
| `GET` | `/expenses` | Search and list, one page at a time | `200` |
| `GET` | `/expenses/{id}` | Get one | `200`, or `404` |
| `PUT` | `/expenses/{id}` | Replace all of it | `200`, or `404` |
| `PATCH` | `/expenses/{id}` | Change some fields | `200`, or `404` |
| `DELETE` | `/expenses/{id}` | Remove it | `204`, or `404` |
| `GET` | `/reports/summary` | Totals by category and by month | `200` |
| `GET` | `/reports/budgets` | Spending against each budget this month | `200` |
| `GET` | `/budgets` | Every budget | `200` |
| `PUT` | `/budgets/{category}` | Set or change a monthly budget | `200` |
| `DELETE` | `/budgets/{category}` | Remove a budget | `204`, or `404` |
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

## Searching, sorting and pages

`GET /expenses` works like the filters on a shopping website. Every
option is optional, and with none you get the newest 20.

| Option | Example | Meaning |
| --- | --- | --- |
| `category` | `food` | Only one category |
| `date_from`, `date_to` | `2026-10-01` | Spent between these days (both included) |
| `min_amount`, `max_amount` | `5`, `20.50` | Between these amounts (both included) |
| `search` | `brighton` | Text in the title or note, any case |
| `sort` | `date`, `amount`, `title`, `created` | What to sort by |
| `order` | `desc` or `asc` | Biggest/newest first, or smallest/oldest first |
| `limit`, `offset` | `20`, `40` | Page size (1 to 100) and where to start |

```
GET /expenses?category=food&date_from=2026-10-01&sort=amount&limit=2
```

```json
{
  "items": [ {"id": 4, "title": "big shop", "amount": "64.10", ...},
             {"id": 3, "title": "Lunch", "amount": "8.50", ...} ],
  "total": 3,
  "limit": 2,
  "offset": 0,
  "next_offset": 2
}
```

- **Pages.** `total` says how many matched altogether. To get the next page,
  send `next_offset` as the `offset`. It's `null` on the last page. Sending
  5,000 expenses at once would be slow, like printing a whole phone book
  when someone asked for one page.
- **Ties always come out the same way.** Two expenses on the same day are
  also sorted by id, so the same request always gives the same order and
  nothing gets skipped or repeated between pages.
- **The database does the work.** `ExpenseRepository.find()` works for any
  repository by filtering in Python. `SqliteRepository` replaces it with
  SQL, so only one page is ever loaded. The same tests run against both, so
  they always give the same answer.
- **Safe from SQL injection.** Values typed by the user always go into the
  SQL as `?` placeholders, never pasted in. Sort columns are picked from a
  fixed list. Searching for `'; DROP TABLE expenses; --` just finds nothing,
  and there's a test for it.
- **Bad options get a `422`**, like `limit=500`, `sort=colour`, or a
  `date_from` after `date_to`.

## Reports and budgets

```
GET /reports/summary?date_from=2026-10-01&date_to=2026-10-31
```

```json
{
  "count": 4,
  "total": "724.35",
  "average": "181.09",
  "biggest": {"title": "Rent", "amount": "650.00", ...},
  "by_category": {"rent": "650.00", "food": "72.60", "transport": "1.75"},
  "by_month": {"2026-10": "724.35"}
}
```

A budget is like putting money in an envelope marked "food" at the start of
the month. `PUT /budgets/food` with `{"monthly_limit": "200"}` fills the
envelope, and `GET /reports/budgets` shows how much of each one is gone:

```json
{
  "month": "2026-11",
  "budgets": [
    {"category": "food", "monthly_limit": "200.00", "spent": "164.20",
     "remaining": "35.80", "percent_used": "82.1", "state": "close"}
  ]
}
```

| State | Means |
| --- | --- |
| `ok` | Under 80% used |
| `close` | 80% or more used, time to slow down |
| `over` | Spent more than planned. `remaining` goes negative to show by how much |

- **`ReportService` only reads.** It adds up expenses but never changes
  them, so it's its own class, separate from `ExpenseService`. Each class
  has one job.
- **Budgets have their own repository.** `BudgetRepository` is abstract,
  with an in memory version and a SQLite version that uses its own table in
  the same database file. Setting a budget twice just replaces it.
- **`PUT` for budgets.** Sending the same budget twice gives the same
  result, which is exactly what `PUT` is for.

## How it's built

```
routes.py         ->  ExpenseService  ->  ExpenseRepository  ->  InMemory or SQLite
report_routes.py  ->  ReportService   ->  ExpenseRepository (read only)
                                      ->  BudgetRepository   ->  InMemory or SQLite
every route       ->  ApiKeyChecker
every error       ->  errors.py  ->  {"detail", "code", "fields"}
```

- **`query.py`** holds `ExpenseQuery` (the filters) and `Page` (one page of
  results). They know nothing about the web or the database.
- **`routes.py`** has one short function per endpoint. It reads the
  request, asks the service to do the work and returns the answer. No rules
  live here.
- **`schemas.py`** holds the Pydantic models: the shape of the JSON going
  in and out. They're kept apart from `Expense`, so the API's JSON and the
  app's own model can each change without breaking the other.
- **`app.py`** builds the app with `create_app()`. The tests call it with
  their own services, so each test starts with an empty app and a clock it
  controls. **`errors.py`** turns every error into the same shape, and
  **`security.py`** checks API keys.
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
pytest          # 328 tests
pytest --cov    # with a coverage report, fails below 95%
```

The API tests use FastAPI's `TestClient`. It sends real HTTP requests to
the app, but in memory, so no server has to be started.

`test_end_to_end.py` starts the app exactly the way `python -m expense_api`
does, with a real database file and an API key, then uses it like a person
would: adds a month of spending, fixes a typo, sets a budget, restarts the
app and checks nothing was lost.

## Project layout

```
expense_api/
    models.py             Expense, Category and exact money
    exceptions.py         the app's own errors
    repository.py         ExpenseRepository and InMemoryRepository
    sqlite_repository.py  SqliteRepository
    query.py              ExpenseQuery, Page and sorting
    service.py            ExpenseService, the rules
    reports.py            ReportService and summaries
    budgets.py            Budget, BudgetStatus and their repositories
    schemas.py            the JSON going in and out (Pydantic)
    routes.py             the /expenses endpoints
    report_routes.py      the /reports and /budgets endpoints
    security.py           API keys
    errors.py             one shape for every error
    settings.py           settings from environment variables
    app.py                create_app() puts it all together
    main.py               the app the web server runs
tests/                    one test file per part, plus end to end tests
```

## What I learned this week

- Building a REST API with FastAPI: routes, status codes, `PUT` vs `PATCH`
- Pydantic models to check input before any of my code runs
- Dependency injection with `Depends`, for the services and the API key check
- Keeping money exact with `Decimal`, and storing it as whole pennies
- Swapping storage behind an abstract class, and proving it with the same
  tests run against both
- Writing SQL safely: placeholders and a fixed list of sort columns
- Pages of results, and why ties need a second sort key
- API keys, and comparing secrets without leaking timing
- Error responses that are consistent and never leak what's inside
- Settings from environment variables

## Week plan

| Day | Focus |
| --- | --- |
| 1 | Expense model, money, repository and service |
| 2 | FastAPI app with create, read, update and delete endpoints |
| 3 | Saving expenses in SQLite |
| 4 | Filtering, sorting and pages of results |
| 5 | Reports and monthly budgets |
| 6 | API keys and clearer error responses |
| 7 | End to end tests and README |
