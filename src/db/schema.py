"""Normalised PostgreSQL schema for F1 data."""
####
#### Additional Notes on DB Schema
#### 
#### Driver Number can change over time, can be fixed by just using surname (check if this is completely valid i.e. all surnames unique)
#### Circuits can change over time
#### I'm also Ignoring sprint races because I think they're distinct enough from Grand Prix to not be used
#### Note that driver ID is usually just the surname, but not always (e.g. max_verstappen and arvid_linblad), think this is due to surname already being taken?
#### Also note that this isn't fully normalised to 3NF because I'm lazy :), need to deal with some foreign key stuff
#### To Do,
#### classify circuits by "bendiness"/number of straight chunks
#### 

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase): # Can't delete this, used to create tables 
    pass


#### Dimension tables 


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True) 
    year = Column(Integer, unique=True, nullable=False) 
    url = Column(Text)

    races = relationship("Race", back_populates="season")


class Circuit(Base):
    __tablename__ = "circuits"

    id = Column(Integer, primary_key=True, autoincrement=True) 
    circuit_ref = Column(String(100), unique=True, nullable=False)  
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    country = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    url = Column(Text)

    races = relationship("Race", back_populates="circuit")


class Constructor(Base): # Important one 
    __tablename__ = "constructors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    constructor_ref = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    nationality = Column(String(100))
    url = Column(Text)


class Driver(Base): # Important one
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_ref = Column(String(100), unique=True, nullable=False)
    number = Column(Integer) # Note that this is non unique, driver numbers can change over time, e.g. MV 33 -> 1 -> 3
    code = Column(String(10))
    forename = Column(String(100), nullable=False) # Excess info, can be removed 
    surname = Column(String(100), nullable=False) # Excess info, can be removed 
    date_of_birth = Column(Date)
    nationality = Column(String(100))
    url = Column(Text)


#### Fact tables 


class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_year = Column(Integer, ForeignKey("seasons.year"), nullable=False)
    round = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    circuit_ref = Column(String(100), ForeignKey("circuits.circuit_ref"), nullable=False)
    date = Column(Date, nullable=False)
    time = Column(String(20))
    url = Column(Text)

    season = relationship("Season", back_populates="races")
    circuit = relationship("Circuit", back_populates="races")
    results = relationship("RaceResult", back_populates="race")
    lap_times = relationship("LapTime", back_populates="race")
    pit_stops = relationship("PitStop", back_populates="race")

    __table_args__ = (
        UniqueConstraint("season_year", "round", name="uq_race_season_round"),
    )


class RaceResult(Base):
    __tablename__ = "race_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    driver_ref = Column(String(100), ForeignKey("drivers.driver_ref"), nullable=False)
    constructor_ref = Column(String(100), ForeignKey("constructors.constructor_ref"), nullable=False)
    grid = Column(Integer)
    position = Column(Integer)
    position_text = Column(String(10))
    points = Column(Float, default=0)
    laps = Column(Integer)
    status = Column(String(100))
    time_millis = Column(BigInteger)
    fastest_lap_rank = Column(Integer)
    fastest_lap_time = Column(String(20))
    fastest_lap_speed = Column(Float)

    race = relationship("Race", back_populates="results")

    __table_args__ = (
        UniqueConstraint("race_id", "driver_ref", name="uq_result_race_driver"),
        Index("ix_results_race", "race_id"),
    )


class LapTime(Base):
    __tablename__ = "lap_times"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    driver_ref = Column(String(100), ForeignKey("drivers.driver_ref"), nullable=False)
    lap = Column(Integer, nullable=False)
    position = Column(Integer)
    time_millis = Column(BigInteger)
    time_str = Column(String(20))

    race = relationship("Race", back_populates="lap_times")

    __table_args__ = (
        UniqueConstraint("race_id", "driver_ref", "lap", name="uq_lap_race_driver_lap"),
        Index("ix_laps_race_driver", "race_id", "driver_ref"),
    )


class PitStop(Base):
    __tablename__ = "pit_stops"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    driver_ref = Column(String(100), ForeignKey("drivers.driver_ref"), nullable=False)
    stop = Column(Integer, nullable=False)
    lap = Column(Integer, nullable=False)
    time_of_day = Column(String(20))
    duration_millis = Column(BigInteger)

    race = relationship("Race", back_populates="pit_stops")

    __table_args__ = (
        UniqueConstraint("race_id", "driver_ref", "stop", name="uq_pit_race_driver_stop"),
    )


#### OpenF1 telemetry tables 


class TelemetrySample(Base):
    """High-frequency car telemetry from OpenF1."""

    __tablename__ = "telemetry_samples"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(Integer, nullable=False)
    driver_number = Column(Integer, nullable=False)
    date = Column(DateTime, nullable=False)
    speed = Column(Integer)
    rpm = Column(Integer)
    gear = Column(Integer)
    throttle = Column(Integer)
    brake = Column(Integer)
    drs = Column(Integer)

    __table_args__ = (
        UniqueConstraint("session_key", "driver_number", "date", name="uq_telem_session_driver_ts"),
        Index("ix_telem_session", "session_key"),
    )


class SessionInfo(Base):
    """OpenF1 session metadata."""

    __tablename__ = "sessions"

    session_key = Column(Integer, primary_key=True)
    session_name = Column(String(100))
    session_type = Column(String(50))
    meeting_key = Column(Integer)
    location = Column(String(255))
    country_name = Column(String(100))
    date_start = Column(DateTime)
    date_end = Column(DateTime)
    year = Column(Integer, nullable=False)

    __table_args__ = (Index("ix_sessions_year", "year"),)
