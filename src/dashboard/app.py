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

from src.analysis.projections import championship_scenarios
from src.dashboard.theme import ACCENT, FADED, MUTED, PALETTE, style_fig
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


def _sum_points(results: list[dict[str, Any]]) -> float:
    return sum(r["points"] for r in results)


def _count(results: list[dict[str, Any]], max_pos: int) -> int:
    return sum(1 for r in results if r["position"] is not None and r["position"] <= max_pos)


def _avg_finish(results: list[dict[str, Any]]) -> float:
    finishes = [r["position"] for r in results if r["position"] is not None]
    return sum(finishes) / len(finishes) if finishes else 0.0


def render_head_to_head(
    db: F1Database,
    season: int,
    standings: list[dict[str, Any]],
    selected_round: int | None,
) -> None:
    """Side-by-side comparison of two drivers across the season."""
    refs = [str(s["driver_ref"]) for s in standings]
    if len(refs) < 2:
        st.info("Need at least two drivers in this season to compare.")
        return

    col_a, col_b = st.columns(2)
    driver_a = col_a.selectbox("Driver A", refs, index=0)
    driver_b = col_b.selectbox("Driver B", refs, index=1)
    if driver_a == driver_b:
        st.info("Pick two different drivers.")
        return

    results = {ref: db.get_driver_results(season, ref) for ref in (driver_a, driver_b)}
    colours = {driver_a: PALETTE[0], driver_b: PALETTE[1]}

    # ── Comparison tiles (delta on A relative to B) ──────────────────────────
    ra, rb = results[driver_a], results[driver_b]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Points", f"{_sum_points(ra):.0f}", delta=f"{_sum_points(ra) - _sum_points(rb):+.0f}")
    m2.metric("Wins", _count(ra, 1), delta=_count(ra, 1) - _count(rb, 1))
    m3.metric("Podiums", _count(ra, 3), delta=_count(ra, 3) - _count(rb, 3))
    m4.metric(
        "Avg finish",
        f"{_avg_finish(ra):.1f}",
        delta=f"{_avg_finish(ra) - _avg_finish(rb):+.1f}",
        delta_color="inverse",  # a lower average finish is better
    )
    st.caption(f"Deltas are {driver_a} relative to {driver_b}.")

    # ── Cumulative points progression ────────────────────────────────────────
    prog: list[dict[str, Any]] = []
    for ref in (driver_a, driver_b):
        running = 0.0
        for row in results[ref]:
            running += row["points"]
            prog.append({"round": row["round"], "driver": ref, "cumulative": running})
    if prog:
        fig = px.line(
            pd.DataFrame(prog),
            x="round",
            y="cumulative",
            color="driver",
            markers=True,
            color_discrete_map=colours,
        )
        fig.update_layout(xaxis_title="Round", yaxis_title="Cumulative points")
        style_fig(fig, height=320)
        st.plotly_chart(fig, use_container_width=True)

    # ── Finishing position by round (P1 at top) ──────────────────────────────
    pos: list[dict[str, Any]] = [
        {"round": row["round"], "driver": ref, "position": row["position"]}
        for ref in (driver_a, driver_b)
        for row in results[ref]
        if row["position"] is not None
    ]
    if pos:
        fig = px.line(
            pd.DataFrame(pos),
            x="round",
            y="position",
            color="driver",
            markers=True,
            color_discrete_map=colours,
        )
        fig.update_layout(xaxis_title="Round", yaxis_title="Finishing position")
        fig.update_yaxes(autorange="reversed")
        style_fig(fig, height=320)
        st.plotly_chart(fig, use_container_width=True)

    # ── Lap-time distribution for the selected race ──────────────────────────
    if selected_round is not None:
        rows = db.get_lap_time_distribution(season, selected_round)
        pair = [r for r in rows if r["driver_ref"] in (driver_a, driver_b)]
        if pair:
            df = pd.DataFrame(pair)
            df["seconds"] = df["time_millis"] / 1000.0
            fig = px.box(
                df,
                x="driver_ref",
                y="seconds",
                color="driver_ref",
                points="outliers",
                color_discrete_map=colours,
            )
            fig.update_layout(xaxis_title=None, yaxis_title="Lap time (s)")
            style_fig(fig, height=320, show_legend=False)
            st.caption("Lap-time distribution for the race selected in the sidebar.")
            st.plotly_chart(fig, use_container_width=True)


def render_championship_whatif(season: int, standings: list[dict[str, Any]]) -> None:
    """Title projection: who can still mathematically win, given remaining races."""
    if not standings:
        st.info("No standings ingested for this season yet.")
        return

    remaining = int(st.number_input("Remaining races", min_value=0, max_value=24, value=5, step=1))
    scenarios = championship_scenarios(standings, remaining)
    leader_current = scenarios[0]["current"]
    contenders = [s for s in scenarios if s["can_win"]]
    st.caption(
        f"{len(contenders)} of {len(scenarios)} drivers can still mathematically win "
        f"with {remaining} race(s) left (assuming 25 pts/win)."
    )

    # Stacked bar: points already secured + points still available, vs the
    # leader's current total (the line a rival must be able to reach).
    segments: list[dict[str, Any]] = []
    for s in scenarios:
        segments.append({"driver": s["driver_ref"], "segment": "Secured", "points": s["current"]})
        segments.append(
            {
                "driver": s["driver_ref"],
                "segment": "Still available",
                "points": s["max_possible"] - s["current"],
            }
        )
    fig = px.bar(
        pd.DataFrame(segments),
        x="points",
        y="driver",
        color="segment",
        orientation="h",
        color_discrete_map={"Secured": ACCENT, "Still available": FADED},
        category_orders={"driver": [s["driver_ref"] for s in reversed(scenarios)]},
    )
    fig.update_traces(marker_line_width=0)
    fig.update_layout(barmode="stack", xaxis_title="Points", yaxis_title=None)
    fig.add_vline(
        x=leader_current,
        line_width=2,
        line_dash="dash",
        line_color=MUTED,
        annotation_text="Leader threshold",
        annotation_position="top",
    )
    style_fig(fig, height=max(340, 26 * len(scenarios)))
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Bars reaching the dashed line can still catch a stalled leader.")


def render_telemetry(db: F1Database, season: int) -> None:
    """Speed / throttle & brake / gear traces for one driver in an OpenF1 session."""
    sessions = db.get_sessions(season)
    if not sessions:
        st.info("No OpenF1 sessions ingested for this season yet (`f1-pipeline ingest-openf1`).")
        return

    labels = {
        (f"{s['session_name'] or s['session_type'] or 'Session'} — {s['location'] or ''}").strip(
            " —"
        ): s["session_key"]
        for s in sessions
    }
    col_s, col_d = st.columns(2)
    session_key = labels[col_s.selectbox("Session", list(labels))]

    drivers = db.get_telemetry_drivers(session_key)
    if not drivers:
        st.info("No telemetry ingested for this session yet.")
        return
    driver_number = col_d.selectbox("Car number", drivers)

    rows = db.get_telemetry(session_key, driver_number, limit=5000)
    if not rows:
        st.info("No telemetry samples for this driver.")
        return

    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["date"], format="mixed")
    df["elapsed"] = (df["t"] - df["t"].min()).dt.total_seconds()
    st.caption(f"{len(df):,} samples · car #{driver_number}")

    speed = px.line(df, x="elapsed", y="speed")
    speed.update_traces(line=dict(color=ACCENT, width=2))
    speed.update_layout(xaxis_title="Elapsed (s)", yaxis_title="Speed (km/h)")
    style_fig(speed, height=260, show_legend=False)
    st.plotly_chart(speed, use_container_width=True)

    pedals = px.line(
        df,
        x="elapsed",
        y=["throttle", "brake"],
        color_discrete_map={"throttle": "#1baf7a", "brake": "#e34948"},
    )
    pedals.update_layout(xaxis_title="Elapsed (s)", yaxis_title="%")
    style_fig(pedals, height=240)
    st.plotly_chart(pedals, use_container_width=True)

    gear = px.line(df, x="elapsed", y="gear", line_shape="hv")
    gear.update_traces(line=dict(color=PALETTE[6], width=2))
    gear.update_layout(xaxis_title="Elapsed (s)", yaxis_title="Gear")
    style_fig(gear, height=220, show_legend=False)
    st.plotly_chart(gear, use_container_width=True)


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

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "🏆 Driver performance",
                "⏱️ Lap-time distributions",
                "🛞 Race strategy",
                "📈 Telemetry",
                "🆚 Head-to-head",
                "🔮 What-if",
            ]
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
        with tab4:
            render_telemetry(db, season)
        with tab5:
            render_head_to_head(db, season, standings, selected_round)
        with tab6:
            render_championship_whatif(season, standings)


if __name__ == "__main__":
    main()
