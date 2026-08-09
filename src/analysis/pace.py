"""Pace-metric logic — pure functions over lap-time rows, no DB or I/O."""

from __future__ import annotations

import statistics
from typing import Any


def pace_metrics(lap_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarise per-driver pace from lap-time rows.

    ``lap_rows`` are ``{"driver_ref", "lap", "time_millis"}`` dicts (as returned
    by ``F1Database.get_lap_time_distribution``). For each driver returns their
    best and median lap, lap-time standard deviation (consistency — lower is
    steadier), lap count, and ``delta_millis`` (their best lap minus the fastest
    lap of the whole race). Sorted by best lap, fastest first.
    """
    by_driver: dict[str, list[int]] = {}
    for row in lap_rows:
        if row.get("time_millis") is None:
            continue
        by_driver.setdefault(str(row["driver_ref"]), []).append(int(row["time_millis"]))

    metrics: list[dict[str, Any]] = []
    for ref, times in by_driver.items():
        metrics.append(
            {
                "driver_ref": ref,
                "best_millis": min(times),
                "median_millis": int(statistics.median(times)),
                "std_millis": statistics.pstdev(times) if len(times) > 1 else 0.0,
                "laps": len(times),
            }
        )
    if not metrics:
        return []

    fastest = min(m["best_millis"] for m in metrics)
    for m in metrics:
        m["delta_millis"] = m["best_millis"] - fastest
    metrics.sort(key=lambda m: m["best_millis"])
    return metrics
