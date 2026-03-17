"""CLI entrypoint for the F1 data pipeline."""

from __future__ import annotations

import sys

import click
import logging

import structlog

from src.config import settings
from src.db.engine import engine
from src.db.queries import F1Database
from src.db.schema import Base
from src.pipeline.ingest import ingest_season, ingest_telemetry

# Map string log level to Python logging int (e.g. "INFO" -> 20)
_log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(_log_level),
)
logger = structlog.get_logger(__name__)


@click.group()
def main() -> None:
    """F1 Data Pipeline — ingest race telemetry, timing and results."""


@main.command()
def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(engine)
    click.echo("Database tables created.")


@main.command()
@click.option("--season", "-s", required=True, type=int, help="Season year (e.g. 2023)")
def ingest_ergast(season: int) -> None:
    """Ingest a full season of Ergast historical data."""
    logger.info("cli_ingest_ergast", season=season)
    try:
        counts = ingest_season(season)
        click.echo(f"Season {season} ingested successfully:")
        for table, n in counts.items():
            click.echo(f"  {table}: {n} rows")
    except Exception as exc:
        logger.error("ingest_failed", season=season, error=str(exc))
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.option("--year", "-y", required=True, type=int, help="Year to ingest telemetry for")
@click.option("--session-key", "-k", multiple=True, type=int, help="Specific session keys")
def ingest_openf1(year: int, session_key: tuple[int, ...]) -> None:
    """Ingest OpenF1 telemetry data for a season."""
    logger.info("cli_ingest_openf1", year=year)
    try:
        keys = list(session_key) if session_key else None
        counts = ingest_telemetry(year, keys)
        click.echo(f"OpenF1 data for {year} ingested successfully:")
        for table, n in counts.items():
            click.echo(f"  {table}: {n} rows")
    except Exception as exc:
        logger.error("ingest_failed", year=year, error=str(exc))
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
def ingest_all(season: int) -> None:
    """Ingest both Ergast and OpenF1 data for a season."""
    logger.info("cli_ingest_all", season=season)
    try:
        ergast_counts = ingest_season(season)
        openf1_counts = ingest_telemetry(season)
        click.echo(f"Full ingest for {season} complete:")
        for table, n in {**ergast_counts, **openf1_counts}.items():
            click.echo(f"  {table}: {n} rows")
    except Exception as exc:
        logger.error("ingest_failed", season=season, error=str(exc))
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.group()
def query() -> None:
    """Query ingested F1 data."""


@query.command()
def seasons() -> None:
    """List all ingested seasons."""
    with F1Database() as db:
        for year in db.get_seasons():
            click.echo(year)


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
def drivers(season: int) -> None:
    """List drivers for a season."""
    with F1Database() as db:
        for d in db.get_drivers(season):
            click.echo(f"{d['code'] or '---':>3}  {d['forename']} {d['surname']}  ({d['nationality']})")


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
def races(season: int) -> None:
    """List races for a season."""
    with F1Database() as db:
        for r in db.get_races(season):
            click.echo(f"R{r['round']:02d}  {r['date']}  {r['name']}")


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
@click.option("--round", "-r", "round_num", required=True, type=int, help="Race round number")
def results(season: int, round_num: int) -> None:
    """Show finishing order for a race."""
    with F1Database() as db:
        for r in db.get_race_results(season, round_num):
            pos = r["position_text"] or "?"
            click.echo(
                f"P{pos:>2}  {r['driver_ref']:<20} {r['constructor_ref']:<20} "
                f"{r['points']:5.1f}pts  {r['status']}"
            )


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
def standings(season: int) -> None:
    """Show driver championship standings for a season."""
    with F1Database() as db:
        for i, row in enumerate(db.get_driver_standings(season), 1):
            click.echo(f"{i:>2}. {row['driver_ref']:<20} {row['total_points']:6.1f}pts  ({row['races']} races)")


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
def constructor_standings(season: int) -> None:
    """Show constructor championship standings for a season."""
    with F1Database() as db:
        for i, row in enumerate(db.get_constructor_standings(season), 1):
            click.echo(f"{i:>2}. {row['constructor_ref']:<20} {row['total_points']:6.1f}pts")


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
@click.option("--round", "-r", "round_num", required=True, type=int, help="Race round number")
@click.option("--driver", "-d", default=None, help="Filter by driver ref")
def laps(season: int, round_num: int, driver: str | None) -> None:
    """Show lap times for a race."""
    with F1Database() as db:
        for lt in db.get_lap_times(season, round_num, driver):
            time_display = lt["time_str"] or "N/A"
            click.echo(f"{lt['driver_ref']:<20} Lap {lt['lap']:>2}  P{lt['position'] or '?':>2}  {time_display}")


@query.command()
@click.option("--season", "-s", required=True, type=int, help="Season year")
@click.option("--round", "-r", "round_num", required=True, type=int, help="Race round number")
@click.option("--driver", "-d", default=None, help="Filter by driver ref")
def pits(season: int, round_num: int, driver: str | None) -> None:
    """Show pit stops for a race."""
    with F1Database() as db:
        for ps in db.get_pit_stops(season, round_num, driver):
            click.echo(
                f"{ps['driver_ref']:<20} Stop {ps['stop']}  Lap {ps['lap']:>2}  {ps['time_of_day'] or ''}"
            )


@query.command()
@click.option("--year", "-y", required=True, type=int, help="Year")
def sessions(year: int) -> None:
    """List OpenF1 sessions for a year."""
    with F1Database() as db:
        for s in db.get_sessions(year):
            click.echo(
                f"{s['session_key']}  {s['session_type'] or '':>12}  "
                f"{s['location'] or '':<25} {s['date_start'] or ''}"
            )


if __name__ == "__main__":
    main()
