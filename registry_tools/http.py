"""JSON requests with retries for rate limits and server errors (SPEC-02 §3.2, §3.3)."""

import time
from functools import wraps
from typing import Any, Callable, Optional

import httpx

MAX_WAIT_SECONDS = 120.0


class CollectError(Exception):
    """A source still failed after retries; the caller keeps the previous metrics (SPEC-02 §3.5)."""


def _rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    return response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0"


def _wait_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after", "")
    if retry_after.isdigit():
        return min(float(retry_after), MAX_WAIT_SECONDS)
    reset = response.headers.get("x-ratelimit-reset", "")
    if reset.isdigit():
        return min(max(float(reset) - time.time(), 1.0), MAX_WAIT_SECONDS)
    return min(2.0 ** attempt, MAX_WAIT_SECONDS)


def request_json(http: httpx.Client, method: str, url: str, *, sleep: Callable[[float], None] = time.sleep,
                 retries: int = 3, **kwargs: Any) -> Optional[Any]:
    """The parsed body, or None for a 404. Raises CollectError once `retries` retries are used up."""
    for attempt in range(retries + 1):
        try:
            response = http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise CollectError(f"{method} {url}: {exc}") from exc
            sleep(min(2.0 ** attempt, MAX_WAIT_SECONDS))
            continue
        if response.status_code == 404:
            return None
        if _rate_limited(response) or response.status_code >= 500:
            if attempt == retries:
                raise CollectError(f"{method} {url}: HTTP {response.status_code} after {retries} retries")
            sleep(_wait_seconds(response, attempt))
            continue
        if response.status_code >= 400:
            raise CollectError(f"{method} {url}: HTTP {response.status_code}")
        try:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
            return body
        except ValueError as exc:
            if attempt == retries:
                raise CollectError(f"{method} {url}: invalid JSON response after {retries} retries") from exc
            sleep(min(2.0 ** attempt, MAX_WAIT_SECONDS))
    raise AssertionError("unreachable")


def checked_response(function):
    """Malformed source payloads participate in per-pipeline stale carry-over."""
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise CollectError(f"{function.__qualname__}: malformed source response") from exc
    return checked


def source_count(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("expected a nonnegative integer count")
    return value
