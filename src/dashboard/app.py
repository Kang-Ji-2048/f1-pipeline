"""Interactive F1 dashboard.

Run with::

    streamlit run src/dashboard/app.py

Reads from the same PostgreSQL database as the pipeline (via ``DATABASE_URL``)
and renders three views: driver performance, lap-time distributions, and race
strategy (stints and pit stops).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.theme import ACCENT, FADED, PALETTE, style_fig
from src.db.queries import F1Database


def _load_seasons() -> list[int]:
    with F1Database() as db:
        return db.get_seasons()


def render_driver_performance(
    db: F1Database,
    season: int,
    standings: list[dict[str, Any]],
    races: list[dict[str, Any]],
) -> None:
    """Championship standings plus cumulative points progression per round."""
    if not standings:
        st.info("No results ingested for this season yet.")
        return

    left, right = st.columns([1, 1], gap="large")

    # ── Standings: single-hue horizontal bar, sorted, with direct labels ──────
    with left:
        st.markdown("**Championship standings**")
        df = pd.DataFrame(standings).sort_values("total_points")
        fig = px.bar(df, x="total_points", y="driver_ref", orientation="h", text="total_points")
        fig.update_traces(
            marker_color=ACCENT,
            texttemplate="%{text:.0f}",
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.0f} pts<extra></extra>",
        )
        fig.update_layout(xaxis_title="Points", yaxis_title=None)
        style_fig(fig, height=max(320, 24 * len(df)), show_legend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Points progression: highlight the top 6, fade the rest ────────────────
    with right:
        st.markdown("**Points progression by round**")
        top6 = [str(s["driver_ref"]) for s in standings[:6]]
        running: dict[str, float] = {}
        series: dict[str, dict[str, list[float]]] = {}
        for race in races:
            rnd = float(race["round"])
            for result in db.get_race_results(season, race["round"]):
                ref = str(result["driver_ref"])
                running[ref] = running.get(ref, 0.0) + float(result["points"] or 0.0)
                pt = series.setdefault(ref, {"x": [], "y": []})
                pt["x"].append(rnd)
                pt["y"].append(running[ref])

        if series:
            fig = go.Figure()
            for ref, pts in series.items():  # faded first, so highlights draw on top
                if ref not in top6:
                    fig.add_trace(
                        go.Scatter(
                            x=pts["x"],
                            y=pts["y"],
                            mode="lines",
                            line=dict(color=FADED, width=1),
                            showlegend=False,
                            hoverinfo="skip",
                        )
                    )
            for ref in top6:
                if ref in series:
                    fig.add_trace(
                        go.Scatter(
                            x=series[ref]["x"],
                            y=series[ref]["y"],
                            mode="lines+markers",
                            name=ref,
                            line=dict(color=PALETTE[top6.index(ref)], width=2),
                            marker=dict(size=7),
                            hovertemplate=f"{ref} · R%{{x:.0f}}: %{{y:.0f}} pts<extra></extra>",
                        )
                    )
            fig.update_layout(xaxis_title="Round", yaxis_title="Cumulative points")
            style_fig(fig, height=max(320, 24 * len(df)))
            st.plotly_chart(fig, use_container_width=True)


def render_lap_time_distributions(db: F1Database, season: int, round_num: int) -> None:
    """Box plot of lap-time distribution per driver for the selected race."""
    rows = db.get_lap_time_distribution(season, round_num)
    if not rows:
        st.info("No lap-time data ingested for this race yet.")
        return

    df = pd.DataFrame(rows)
    df["seconds"] = df["time_millis"] / 1000.0
    order = df.groupby("driver_ref")["seconds"].median().sort_values(ascending=False).index.tolist()

    fig = px.box(
        df,
        x="seconds",
        y="driver_ref",
        orientation="h",
        points="outliers",
        category_orders={"driver_ref": order},
    )
    fig.update_traces(marker_color=ACCENT, line_color=ACCENT, marker_size=4)
    fig.update_layout(xaxis_title="Lap time (s)", yaxis_title=None)
    style_fig(fig, height=max(340, 26 * len(order)), show_legend=False)
    st.caption("Sorted slowest→fastest by median lap. Tighter boxes = more consistent pace.")
    st.plotly_chart(fig, use_container_width=True)


def render_race_strategy(db: F1Database, season: int, round_num: int) -> None:
    """Stint lengths and pit-stop laps for the selected race."""
    stints = db.get_stints(season, round_num)
    if not stints:
        st.info("No stint/pit data ingested for this race yet.")
        return

    df = pd.DataFrame(stints)
    df["Stint"] = "Stint " + df["stint"].astype(str)
    fig = px.bar(
        df,
        x="laps",
        y="driver_ref",
        color="Stint",
        orientation="h",
        hover_data={"start_lap": True, "end_lap": True, "driver_ref": False},
    )
    fig.update_traces(marker_line_width=0)
    fig.update_layout(barmode="stack", xaxis_title="Laps", yaxis_title=None)
    style_fig(fig, height=max(340, 26 * df["driver_ref"].nunique()))
    st.caption("Each segment is a stint between pit stops; total bar length is race distance.")
    st.plotly_chart(fig, use_container_width=True)

    pits = db.get_pit_stops(season, round_num)
    if pits:
        with st.expander(f"Pit stops ({len(pits)})"):
            pit_df = pd.DataFrame(pits)[["driver_ref", "stop", "lap", "time_of_day"]]
            st.dataframe(
                pit_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "driver_ref": "Driver",
                    "stop": "Stop #",
                    "lap": "Lap",
                    "time_of_day": "Time of day",
                },
            )


def main() -> None:
    st.set_page_config(page_title="F1 Data Dashboard", page_icon="🏎️", layout="wide")
    st.markdown(
        """
        <style>
          .block-container {padding-top: 2.2rem; padding-bottom: 2rem;}
          [data-testid="stMetricValue"] {font-size: 1.4rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("🏎️ F1 Data Dashboard")

    seasons = _load_seasons()
    if not seasons:
        st.warning("No seasons ingested yet. Run the pipeline first (`f1-pipeline ingest-all`).")
        return

    season = st.sidebar.selectbox("Season", seasons, index=len(seasons) - 1)

    with F1Database() as db:
        standings = db.get_driver_standings(season)
        constructors = db.get_constructor_standings(season)
        races = db.get_races(season)

        # ── Season summary tiles ─────────────────────────────────────────────
        leader = standings[0] if standings else None
        top_team = constructors[0] if constructors else None
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Points leader", str(leader["driver_ref"]) if leader else "—")
        c2.metric("Leader points", f"{leader['total_points']:.0f}" if leader else "—")
        c3.metric("Leading constructor", str(top_team["constructor_ref"]) if top_team else "—")
        c4.metric("Races", len(races))
        st.divider()

        race_labels = {f"R{r['round']:02d} — {r['name']}": r["round"] for r in races}
        selected_round = None
        if race_labels:
            label = st.sidebar.selectbox("Race", list(race_labels))
            selected_round = race_labels[label]

        tab1, tab2, tab3 = st.tabs(
            ["🏆 Driver performance", "⏱️ Lap-time distributions", "🛞 Race strategy"]
        )
        with tab1:
            render_driver_performance(db, season, standings, races)
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
