"""Tests for championship projection logic (pure functions)."""

from __future__ import annotations

from src.analysis.projections import championship_scenarios


def _standings(*pairs: tuple[str, float]) -> list[dict[str, object]]:
    return [{"driver_ref": ref, "total_points": pts} for ref, pts in pairs]


class TestChampionshipScenarios:
    def test_empty_standings(self):
        assert championship_scenarios([], remaining_races=5) == []

    def test_contender_can_still_catch_a_stalled_leader(self):
        scen = championship_scenarios(_standings(("ver", 100), ("nor", 80)), remaining_races=1)
        nor = next(s for s in scen if s["driver_ref"] == "nor")
        assert nor["max_possible"] == 105  # 80 + 1*25
        assert nor["gap_to_leader"] == 20
        assert nor["can_win"] is True

    def test_driver_mathematically_eliminated(self):
        scen = championship_scenarios(_standings(("ver", 100), ("nor", 80)), remaining_races=0)
        nor = next(s for s in scen if s["driver_ref"] == "nor")
        assert nor["max_possible"] == 80
        assert nor["can_win"] is False

    def test_leader_always_in_contention_and_sorted_desc(self):
        scen = championship_scenarios(
            _standings(("nor", 80), ("ver", 100), ("lec", 60)), remaining_races=2
        )
        assert [s["driver_ref"] for s in scen] == ["ver", "nor", "lec"]
        assert scen[0]["can_win"] is True
        assert scen[0]["gap_to_leader"] == 0

    def test_custom_points_for_win(self):
        scen = championship_scenarios(
            _standings(("ver", 100), ("nor", 70)), remaining_races=1, points_for_win=26
        )
        nor = next(s for s in scen if s["driver_ref"] == "nor")
        assert nor["max_possible"] == 96  # 70 + 26
        assert nor["can_win"] is False
