"""Shared HTTP helpers for external registry integrations."""

from __future__ import annotations

from typing import Mapping, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


def build_retry_session(
    *,
    headers: Optional[Mapping[str, str]] = None,
    total_retries: int = 4,
    backoff_factor: float = 0.6,
    timeout_status_codes: tuple[int, ...] = DEFAULT_RETRY_STATUS_CODES,
) -> requests.Session:
    """Create a requests session with sensible retry/backoff for flaky public APIs."""
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=list(timeout_status_codes),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if headers:
        session.headers.update(dict(headers))
    return session

