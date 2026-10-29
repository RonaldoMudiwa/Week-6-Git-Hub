# Expense REST API

A web API for recording and reporting on spending, written in Python with
[FastAPI](https://fastapi.tiangolo.com). Other programs, like a website or a
phone app, will be able to add, change and look up expenses by sending it
HTTP requests.

Project 6 of a 12 week portfolio. Week 1 was an expense tracker for the
terminal. This week the same idea becomes a proper web API.

## Status

Day 1 of 7. The expense model, exact money handling, the repository and
the service layer that the API will sit on top of.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate           # macOS or Linux: source .venv/bin/activate
pip install -r requirements.txt

pytest                           # run the tests
```

Needs Python 3.10 or newer.

## How it's built

```
the API (from Day 2)  ->  ExpenseService  ->  ExpenseRepository  ->  storage
```

- **`Expense`** is one thing that was paid for: a title, an amount, a
  category, the date it was spent and an optional note. It's frozen, so it
  can't be changed by accident, and it checks its own values when it's made.
- **`ExpenseRepository`** is an abstract class that says what storage must
  do: add, get, list, update and delete. `InMemoryRepository` keeps
  everything in a dictionary for now. A SQLite version comes later as
  another class, and nothing above it will need to change.
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
pytest          # 57 tests
pytest --cov    # with a coverage report, fails below 95%
```

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
