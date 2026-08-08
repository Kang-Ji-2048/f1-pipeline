"""Base HTTP client with fault-tolerant retry logic."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

logger = structlog.get_logger(__name__)


class APIClient:
    """Resilient HTTP client with exponential-backoff retries."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._min_interval = settings.RATE_LIMIT_DELAY
        self._last_request = 0.0
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def _throttle(self) -> None:
        """Space requests apart to stay under the API's rate limit."""
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    @staticmethod
    def _parse_retry_after(resp: httpx.Response) -> float:
        """Read the Retry-After header (seconds); fall back to a sane default."""
        value = resp.headers.get("Retry-After", "")
        if value.isdigit():
            return float(value)
        return 2.0

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF, min=1, max=60),
        reraise=True,
    )
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._throttle()
        logger.debug("api_request", url=f"{self._base_url}{path}", params=params)
        resp = self._client.get(path, params=params)
        if resp.status_code == 429:
            retry_after = self._parse_retry_after(resp)
            logger.warning("rate_limited", url=f"{self._base_url}{path}", retry_after=retry_after)
            time.sleep(retry_after)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> APIClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
