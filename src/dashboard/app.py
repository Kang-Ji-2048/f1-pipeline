"""Interactive F1 dashboard.

Run with::

    streamlit run src/dashboard/app.py

Reads from the same PostgreSQL database as the pipeline (via ``DATABASE_URL``)
and renders three views: driver performance, lap-time distributions, and race
strategy (stints and pit stops).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.db.queries import F1Database


def _load_seasons() -> list[int]:
    with F1Database() as db:
        return db.get_seasons()


def render_driver_performance(db: F1Database, season: int) -> None:
    """Championship standings plus cumulative points progression per round."""
    st.subheader("Driver performance metrics")

    standings = db.get_driver_standings(season)
    if not standings:
        st.info("No results ingested for this season yet.")
        return

    standings_df = pd.DataFrame(standings)
    fig = px.bar(
        standings_df,
        x="driver_ref",
        y="total_points",
        title=f"{season} driver championship — total points",
        labels={"driver_ref": "Driver", "total_points": "Points"},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Cumulative points progression across the season's rounds.
    races = db.get_races(season)
    progression: list[dict[str, object]] = []
    running: dict[str, float] = {}
    for race in races:
        for result in db.get_race_results(season, race["round"]):
            ref = result["driver_ref"]
            running[ref] = running.get(ref, 0.0) + (result["points"] or 0.0)
            progression.append(
                {"round": race["round"], "driver_ref": ref, "cumulative_points": running[ref]}
            )
    if progression:
        prog_df = pd.DataFrame(progression)
        line = px.line(
            prog_df,
            x="round",
            y="cumulative_points",
            color="driver_ref",
            markers=True,
            title=f"{season} points progression by round",
            labels={"round": "Round", "cumulative_points": "Cumulative points"},
        )
        st.plotly_chart(line, use_container_width=True)


def render_lap_time_distributions(db: F1Database, season: int, round_num: int) -> None:
    """Box plot of lap-time distribution per driver for the selected race."""
    st.subheader("Lap-time distributions")

    rows = db.get_lap_time_distribution(season, round_num)
    if not rows:
        st.info("No lap-time data ingested for this race yet.")
        return

    df = pd.DataFrame(rows)
    df["seconds"] = df["time_millis"] / 1000.0
    fig = px.box(
        df,
        x="driver_ref",
        y="seconds",
        points="outliers",
        title="Lap-time distribution by driver",
        labels={"driver_ref": "Driver", "seconds": "Lap time (s)"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_race_strategy(db: F1Database, season: int, round_num: int) -> None:
    """Stint lengths and pit-stop laps for the selected race."""
    st.subheader("Race strategy patterns")

    stints = db.get_stints(season, round_num)
    if not stints:
        st.info("No stint/pit data ingested for this race yet.")
        return

    df = pd.DataFrame(stints)
    fig = px.bar(
        df,
        x="laps",
        y="driver_ref",
        color="stint",
        orientation="h",
        title="Stint lengths by driver",
        labels={"laps": "Laps in stint", "driver_ref": "Driver", "stint": "Stint"},
    )
    st.plotly_chart(fig, use_container_width=True)

    pits = db.get_pit_stops(season, round_num)
    if pits:
        st.caption("Pit stops")
        st.dataframe(pd.DataFrame(pits), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="F1 Data Dashboard", page_icon="🏎️", layout="wide")
    st.title("🏎️ F1 Data Dashboard")

    seasons = _load_seasons()
    if not seasons:
        st.warning("No seasons ingested yet. Run the pipeline first (`f1-pipeline ingest-all`).")
        return

    season = st.sidebar.selectbox("Season", seasons, index=len(seasons) - 1)

    with F1Database() as db:
        races = db.get_races(season)
        race_labels = {f"R{r['round']:02d} — {r['name']}": r["round"] for r in races}
        selected_round = None
        if race_labels:
            label = st.sidebar.selectbox("Race", list(race_labels))
            selected_round = race_labels[label]

        tab1, tab2, tab3 = st.tabs(
            ["Driver performance", "Lap-time distributions", "Race strategy"]
        )
        with tab1:
            render_driver_performance(db, season)
        with tab2:
            if selected_round is not None:
                render_lap_time_distributions(db, season, selected_round)
            else:
                st.info("No races available for this season.")
        with tab3:
            if selected_round is not None:
                render_race_strategy(db, season, selected_round)
            else:
                st.info("No races available for this season.")


if __name__ == "__main__":
    main()
