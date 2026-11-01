"""The endpoints: which URL does what.

    POST   /expenses        add one         -> 201 Created
    GET    /expenses        search and list -> 200, one page at a time
    GET    /expenses/{id}   get one         -> 200, or 404
    PUT    /expenses/{id}   replace one     -> 200, or 404
    PATCH  /expenses/{id}   change some     -> 200, or 404
    DELETE /expenses/{id}   remove one      -> 204 No Content, or 404

Each function is short on purpose. It reads the request, asks the service
to do the work, and turns the answer into JSON. The rules live in the
service, not here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, Response, status

from .models import Category
from .query import DEFAULT_LIMIT, MAX_LIMIT, ExpenseQuery, Order, SortField
from .schemas import ErrorOut, ExpenseChanges, ExpenseIn, ExpenseOut, ExpensePage
from .service import ExpenseService

NOT_FOUND = {404: {"model": ErrorOut, "description": "No expense has that id"}}

router = APIRouter(prefix="/expenses", tags=["expenses"])


def get_service(request: Request) -> ExpenseService:
    """Hands each endpoint the one shared service.

    FastAPI calls this for us through Depends(). Tests can swap in their own
    service when they build the app, without touching any endpoint.
    """
    return request.app.state.service


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ExpenseOut)
def create_expense(body: ExpenseIn, response: Response,
                   service: ExpenseService = Depends(get_service)) -> ExpenseOut:
    expense = service.create(**body.model_dump())
    # Tells the caller where the new expense lives, as REST APIs usually do.
    response.headers["Location"] = f"/expenses/{expense.id}"
    return ExpenseOut.of(expense)


def search_options(
    category: Category | None = None,
    date_from: date | None = Query(None, description="On or after this day"),
    date_to: date | None = Query(None, description="On or before this day"),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(None, max_length=100, description="Text in the title or note"),
    sort: SortField = SortField.DATE,
    order: Order = Order.DESC,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> ExpenseQuery:
    """Turns the ?category=food&sort=amount... part of the URL into a query.
    FastAPI checks each value's type before this even runs."""
    return ExpenseQuery(category, date_from, date_to, min_amount, max_amount, search,
                        sort, order, limit, offset)


@router.get("", response_model=ExpensePage)
def list_expenses(query: ExpenseQuery = Depends(search_options),
                  service: ExpenseService = Depends(get_service)) -> ExpensePage:
    """For example /expenses?category=food&date_from=2026-10-01&sort=amount&limit=10"""
    return ExpensePage.of(service.search(query))


@router.get("/{expense_id}", response_model=ExpenseOut, responses=NOT_FOUND)
def get_expense(expense_id: int, service: ExpenseService = Depends(get_service)) -> ExpenseOut:
    return ExpenseOut.of(service.get(expense_id))


@router.put("/{expense_id}", response_model=ExpenseOut, responses=NOT_FOUND)
def replace_expense(expense_id: int, body: ExpenseIn,
                    service: ExpenseService = Depends(get_service)) -> ExpenseOut:
    """Every field is replaced. A field left out goes back to its default."""
    values = body.model_dump()
    if values["spent_on"] is None:
        values["spent_on"] = service.today()
    return ExpenseOut.of(service.update(expense_id, **values))


@router.patch("/{expense_id}", response_model=ExpenseOut, responses=NOT_FOUND)
def change_expense(expense_id: int, body: ExpenseChanges,
                   service: ExpenseService = Depends(get_service)) -> ExpenseOut:
    # exclude_unset keeps only the fields the caller actually sent.
    return ExpenseOut.of(service.update(expense_id, **body.model_dump(exclude_unset=True)))


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_expense(expense_id: int, service: ExpenseService = Depends(get_service)) -> Response:
    service.delete(expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
