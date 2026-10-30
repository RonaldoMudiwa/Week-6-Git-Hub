"""Lets the package run as a program: python -m expense_api"""

import uvicorn

uvicorn.run("expense_api.main:app", host="127.0.0.1", port=8000)
