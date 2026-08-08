"""OpenF1 API client for live telemetry and session data."""

from __future__ import annotations

from typing import Any

import structlog

from src.api.base import APIClient
from src.config import settings
from src.models.validators import SessionData, TelemetryData

logger = structlog.get_logger(__name__)


class OpenF1Client:
    """Fetches telemetry and session data from the OpenF1 API."""

    def __init__(self) -> None:
        self._client = APIClient(settings.OPENF1_BASE_URL)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenF1Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_sessions(self, year: int) -> list[SessionData]:
        raw = self._client.get("/sessions", params={"year": year})
        sessions = []
        for s in raw:
            s["year"] = year
            sessions.append(SessionData.model_validate(s))
        logger.info("openf1_sessions", year=year, count=len(sessions))
        return sessions

    def get_car_data(
        self,
        session_key: int,
        driver_number: int | None = None,
    ) -> list[TelemetryData]:
        """Fetch car telemetry for a session, optionally filtered by driver."""
        params: dict[str, int] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        raw = self._client.get("/car_data", params=params)
        samples = [TelemetryData.model_validate(s) for s in raw]
        logger.info(
            "openf1_telemetry",
            session_key=session_key,
            driver=driver_number,
            count=len(samples),
        )
        return samples

    def get_latest_car_data(
        self,
        session_key: int | str = "latest",
        after: str | None = None,
    ) -> list[TelemetryData]:
        """Fetch car telemetry for live polling.

        ``session_key`` accepts the literal ``"latest"`` to follow the currently
        running session. When ``after`` (an ISO timestamp) is given, only samples
        with ``date`` strictly greater than it are returned, so a poller can pull
        just the newly-arrived rows each iteration.
        """
        params: dict[str, Any] = {"session_key": session_key}
        if after is not None:
            params["date>"] = after
        raw = self._client.get("/car_data", params=params)
        samples = [TelemetryData.model_validate(s) for s in raw]
        logger.info(
            "openf1_latest_telemetry",
            session_key=session_key,
            after=after,
            count=len(samples),
        )
        return samples
