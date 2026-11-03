"""API keys: a password for programs.

When keys are set, every request has to send one in an X-API-Key header,
like showing a membership card at the door. With no keys set (the
default, handy when trying it out on your own computer) the door is open.

    EXPENSE_API_KEYS=key-one,key-two
"""

from __future__ import annotations

import hmac
from typing import Iterable

from fastapi import Security
from fastapi.security import APIKeyHeader

from .errors import UnauthorizedError

HEADER = "X-API-Key"

# auto_error=False means we decide what happens when the header is missing,
# so the error has the same shape as every other one.
_header = APIKeyHeader(name=HEADER, auto_error=False)


class ApiKeyChecker:
    def __init__(self, keys: Iterable[str] = ()) -> None:
        self._keys = tuple(key.strip() for key in keys if key and key.strip())

    @property
    def enabled(self) -> bool:
        return bool(self._keys)

    def is_valid(self, given: str | None) -> bool:
        if not self.enabled:
            return True
        if not given:
            return False
        # compare_digest takes the same time whether the first letter or the
        # last letter is wrong, so nobody can guess a key one letter at a time
        # by timing the answers.
        return any(hmac.compare_digest(given.encode(), key.encode()) for key in self._keys)

    def __call__(self, given: str | None = Security(_header)) -> None:
        """Used as a FastAPI dependency on every protected route."""
        if not self.is_valid(given):
            raise UnauthorizedError(f"A valid API key is needed in the {HEADER} header.")
