"""The app that the web server runs.

    uvicorn expense_api.main:app --reload

Then open http://127.0.0.1:8000/docs to try every endpoint in the browser.
Expenses are saved in data/expenses.db unless EXPENSE_DB says otherwise,
and API keys are read from EXPENSE_API_KEYS (see settings.py).
"""

from .app import create_app
from .settings import Settings, build_reports, build_service

settings = Settings.from_env()
service = build_service(settings)
app = create_app(service, build_reports(settings, service), settings.api_keys)
