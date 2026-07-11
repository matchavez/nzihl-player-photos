"""Shared HTTP session with browser-like headers + a polite 1 req/sec throttle.

esportsdesk (admin.esportsdesk.com) 403s requests with non-browser
User-Agents. One Session is reused across all fetches; a module-level
throttle enforces >=1s between *any* two outbound requests (roster pages,
personnel pages, profile-page fallbacks, and image downloads all share the
same limiter) per the project's "fetch politely" convention.
"""
from __future__ import annotations

import time

import requests

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-NZ,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

MIN_INTERVAL_SECONDS = 1.0

_SESSION: requests.Session | None = None
_last_request_at: float = 0.0


def session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        s.headers.update(_HEADERS)
        _SESSION = s
    return _SESSION


def _throttle() -> None:
    global _last_request_at
    now = time.monotonic()
    wait = MIN_INTERVAL_SECONDS - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0


def fetch_text(url: str, *, timeout: int = 30, retries: int = _MAX_RETRIES) -> str:
    """GET `url`, throttled, and return the response text. Retries on
    network errors / non-2xx (esportsdesk is occasionally flaky under
    sustained request volume — observed during development: a team's
    stats page intermittently comes back with an unexpectedly short/empty
    body despite a normal 200 status). Raises after exhausting retries."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        _throttle()
        try:
            resp = session().get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def fetch_binary(url: str, *, timeout: int = 30, retries: int = _MAX_RETRIES) -> requests.Response:
    """GET `url`, throttled, and return the raw Response (status not raised,
    caller decides success — esportsdesk returns 200 with an HTML error page
    body for a missing image rather than a real 404, so status alone can't
    be trusted; check Content-Type / magic bytes instead). Retries only on
    network-level exceptions, not on any particular status code (a real
    404-equivalent 200 is a valid, final answer, not a transient failure)."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        _throttle()
        try:
            return session().get(url, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_exc  # type: ignore[misc]
