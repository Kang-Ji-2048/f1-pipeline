"""Championship projection logic — pure functions, no DB or I/O."""

from __future__ import annotations

from typing import Any


def championship_scenarios(
    standings: list[dict[str, Any]],
    remaining_races: int,
    points_for_win: int = 25,
) -> list[dict[str, Any]]:
    """Project each driver's title maths from current standings.

    For every driver returns their current points, the maximum still attainable
    (``current + remaining_races * points_for_win``), the gap to the current
    leader, and ``can_win`` — whether they could still finish above the leader's
    *current* total (the standard "mathematically eliminated" test: a driver is
    out once even a stalled leader is out of reach). Sorted by current points,
    descending.
    """
    if not standings:
        return []

    leader_points = max(float(s["total_points"]) for s in standings)
    scenarios: list[dict[str, Any]] = []
    for s in standings:
        current = float(s["total_points"])
        max_possible = current + remaining_races * points_for_win
        scenarios.append(
            {
                "driver_ref": s["driver_ref"],
                "current": current,
                "max_possible": max_possible,
                "gap_to_leader": leader_points - current,
                "can_win": max_possible >= leader_points,
            }
        )
    scenarios.sort(key=lambda r: r["current"], reverse=True)
    return scenarios
