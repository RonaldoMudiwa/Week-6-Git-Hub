"""Endpoints for reports and budgets.

    GET    /reports/summary          totals by category and month
    GET    /reports/budgets          how much of each budget is used this month
    GET    /budgets                  every budget
    PUT    /budgets/{category}       set or change a budget
    DELETE /budgets/{category}       remove a budget
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status

from .exceptions import ExpenseError
from .models import Category
from .reports import ReportService
from .schemas import BudgetIn, BudgetOut, BudgetReportOut, BudgetStatusOut, ErrorOut, SummaryOut

router = APIRouter(tags=["reports and budgets"])


class BudgetNotFoundError(ExpenseError):
    def __init__(self, category: Category) -> None:
        super().__init__(f"There's no budget for {category.value}.")


def get_reports(request: Request) -> ReportService:
    return request.app.state.reports


@router.get("/reports/summary", response_model=SummaryOut)
def summary(date_from: date | None = None, date_to: date | None = None,
            reports: ReportService = Depends(get_reports)) -> SummaryOut:
    """Leave out the dates to sum up everything."""
    return SummaryOut.of(reports.summary(date_from, date_to))


@router.get("/reports/budgets", response_model=BudgetReportOut)
def budget_report(month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", examples=["2026-11"]),
                  reports: ReportService = Depends(get_reports)) -> BudgetReportOut:
    """Spending against each budget for one month. This month if left out."""
    statuses = reports.budget_report(month)
    chosen = month or reports.this_month()
    return BudgetReportOut(month=chosen, budgets=[BudgetStatusOut.of(s) for s in statuses])


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(reports: ReportService = Depends(get_reports)) -> list[BudgetOut]:
    return [BudgetOut.of(b) for b in reports.budgets()]


@router.put("/budgets/{category}", response_model=BudgetOut)
def set_budget(category: Category, body: BudgetIn,
               reports: ReportService = Depends(get_reports)) -> BudgetOut:
    """PUT because setting the same budget twice gives the same result."""
    return BudgetOut.of(reports.set_budget(category, body.monthly_limit))


@router.delete("/budgets/{category}", status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": ErrorOut, "description": "No budget for that category"}})
def remove_budget(category: Category, reports: ReportService = Depends(get_reports)) -> Response:
    if not reports.remove_budget(category):
        raise BudgetNotFoundError(category)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
