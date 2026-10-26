"""Bounded retries for idempotent source reads; never retry malformed payloads."""

from __future__ import annotations

import time
from typing import Any

import requests  # type: ignore[import-untyped]


def get(url: str, **kwargs: Any) -> requests.Response:
    """Retry connection failures, timeouts, HTTP 429 and 5xx at most three times."""
    kwargs.setdefault("timeout", 45)
    for attempt in range(3):
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status != 429 and status < 500:
                raise
            if attempt == 2:
                raise
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
        time.sleep(2**attempt)
    raise RuntimeError("Unreachable retry state")
