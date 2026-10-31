"""The app that the web server runs.

    uvicorn expense_api.main:app --reload

Then open http://127.0.0.1:8000/docs to try every endpoint in the browser.
Expenses are saved in data/expenses.db unless EXPENSE_DB says otherwise.
"""

from .app import create_app
from .settings import Settings, build_service

app = create_app(build_service(Settings.from_env()))
