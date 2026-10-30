"""The app that the web server runs.

    uvicorn expense_api.main:app --reload

Then open http://127.0.0.1:8000/docs to try every endpoint in the browser.
"""

from .app import create_app

app = create_app()
