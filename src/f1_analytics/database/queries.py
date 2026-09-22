"""Read-only query helpers over f1.db (canonical historical store)."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from ..data import connect_sqlite


def _conn() -> sqlite3.Connection:
    return connect_sqlite()


def query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a SELECT. Dict params are positional by insertion order."""
    con = _conn()
    try:
        if params:
            params = tuple(params.values())
        return pd.read_sql(sql, con, params=params or None)
    finally:
        con.close()


def driver_sessions(driver_id: int | None = None, name: str | None = None) -> pd.DataFrame:
    sql = """
        SELECT r.year, r.round, r.name AS race_name, c.name AS circuit,
               res.grid, CAST(res.position AS TEXT) AS position, res.positionOrder, res.points,
               res.laps, s.status, res.driverId
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        JOIN circuits c ON r.circuitId = c.circuitId
        JOIN status s ON res.statusId = s.statusId
        JOIN drivers d ON res.driverId = d.driverId
        WHERE (? IS NULL OR res.driverId = ?)
          AND (? IS NULL OR lower(d.surname) = lower(?) OR lower(d.forename) = lower(?))
        ORDER BY r.year, r.round
    """
    return query(sql, {"1": driver_id, "2": driver_id, "3": name, "4": name, "5": name})


def driver_list() -> pd.DataFrame:
    return query(
        """
        SELECT d.driverId, d.driverRef, d.code, d.forename, d.surname,
               d.nationality, COUNT(r.resultId) AS starts,
               SUM(CASE WHEN res.position = '1' THEN 1 ELSE 0 END) AS wins
        FROM drivers d
        LEFT JOIN results r ON r.driverId = d.driverId
        LEFT JOIN results res ON res.driverId = d.driverId AND res.position = '1'
        GROUP BY d.driverId
        ORDER BY wins DESC, surname
        """
    )


def constructor_list() -> pd.DataFrame:
    return query(
        """
        SELECT c.constructorId, c.name, c.nationality,
               COUNT(res.resultId) AS starts
        FROM constructors c
        LEFT JOIN results res ON res.constructorId = c.constructorId
        GROUP BY c.constructorId
        ORDER BY starts DESC, c.name
        """
    )


def circuit_list() -> pd.DataFrame:
    return query(
        """
        SELECT ci.circuitId, ci.circuitRef, ci.name, ci.location, ci.country,
               COUNT(r.raceId) AS races_held
        FROM circuits ci
        LEFT JOIN races r ON r.circuitId = ci.circuitId
        GROUP BY ci.circuitId
        ORDER BY races_held DESC
        """
    )


def race_calendar() -> pd.DataFrame:
    return query(
        """
        SELECT r.raceId, r.year, r.round, r.name, c.name AS circuit,
               c.circuitRef, r.date
        FROM races r JOIN circuits c ON r.circuitId = c.circuitId
        ORDER BY r.year, r.round
        """
    )


def race_results(race_id: int | None = None, year: int | None = None) -> pd.DataFrame:
    sql = """
        SELECT r.raceId, r.year, r.round, d.driverId, d.code,
               d.forename || ' ' || d.surname AS driver,
               c.name AS constructor, res.grid, res.positionOrder AS position,
               res.points, res.laps, st.status
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        JOIN drivers d ON res.driverId = d.driverId
        JOIN constructors c ON res.constructorId = c.constructorId
        JOIN status st ON res.statusId = st.statusId
        WHERE (? IS NULL OR res.raceId = ?)
          AND (? IS NULL OR r.year = ?)
        ORDER BY r.year, r.round, res.positionOrder
    """
    return query(sql, {"1": race_id, "2": race_id, "3": year, "4": year})


def standings_driver(year: int | None = None) -> pd.DataFrame:
    sql = """
        SELECT ds.*, d.driverRef, d.forename || ' ' || d.surname AS driver
        FROM driver_standings ds
        JOIN races r ON ds.raceId = r.raceId
        JOIN drivers d ON ds.driverId = d.driverId
        WHERE (? IS NULL OR r.year = ?) AND r.round = (
            SELECT MAX(round) FROM races WHERE year = r.year
        )
        ORDER BY ds.position
    """
    return query(sql, {"1": year, "2": year})


def speed_traps() -> pd.DataFrame:
    return query(
        """
        SELECT r.year, l.raceId, l.driverId, l.session,
               d.code, c.name AS constructor, l.speed_trap
        FROM fastf1_laps l
        JOIN races r ON l.raceId = r.raceId
        JOIN drivers d ON d.driverId = l.driverId
        JOIN results res ON res.raceId = l.raceId AND res.driverId = l.driverId
        JOIN constructors c ON c.constructorId = res.constructorId
        WHERE l.speed_trap IS NOT NULL
        """
    )


def lap_pace(session: str = "Race", year_min: int = 2018, year_max: int = 2026) -> pd.DataFrame:
    return query(
        """
        SELECT r.year, l.driverId, d.code, d.forename || ' ' || d.surname AS driver,
               c.name AS constructor, l.time_sec, l.s1, l.s2, l.s3,
               l.is_accurate, l.track_status, l.rainfall
        FROM fastf1_laps l
        JOIN races r ON l.raceId = r.raceId
        JOIN drivers d ON d.driverId = l.driverId
        JOIN results res ON res.raceId = l.raceId AND res.driverId = l.driverId
        JOIN constructors c ON c.constructorId = res.constructorId
        WHERE l.session = ?
          AND l.is_accurate = 1
          AND r.year BETWEEN ? AND ?
        """,
        {"session": session, "year_min": year_min, "year_max": year_max},
    )