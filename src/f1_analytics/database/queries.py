"""Read-only query helpers over f1.db (canonical historical store).

When f1.db is absent, queries transparently fall back to a read-only
in-memory SQLite database built from the tracked Kaggle CSVs (1950-2024).
The in-memory store is never written to disk, so it can never corrupt a
production database. Queries that depend on database-only telemetry
tables (fastf1_laps, session_weather, ...) fail with an actionable
DataNotFoundError explaining that f1.db is required.
"""

from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from typing import Any

import pandas as pd

from ..data import DataNotFoundError, connect_sqlite, db_available, load_kaggle_all

# Telemetry tables exist only in f1.db - they cannot be reconstructed from
# the tracked Kaggle CSV snapshot.
_DB_ONLY_TABLES = frozenset({
    "fastf1_laps", "session_weather", "race_control", "safety_cars",
    "red_flags", "circuit_corners", "results_shared_drives",
})

_CSV_CONN: sqlite3.Connection | None = None
_CSV_MODE = False

_MISSING_TABLE_RE = re.compile(r"no such table:\s*(\w+)")


def data_source() -> dict[str, Any]:
    """Describe which store currently backs the query layer."""
    if db_available():
        from .. import config
        return {
            "mode": "sqlite",
            "db_path": str(config.F1_DB_PATH),
            "csv_fallback": False,
            "note": "",
        }
    return {
        "mode": "csv_fallback",
        "db_path": "",
        "csv_fallback": True,
        "note": "f1.db is missing - using the tracked 1950-2024 CSV snapshot in memory. "
                "2025-2026 and telemetry-dependent features require f1.db.",
    }


def _csv_conn_available() -> bool:
    return _CSV_CONN is not None


def _cs_to_conn(df: pd.DataFrame, con: sqlite3.Connection, name: str) -> None:
    """Write a CSV frame to an in-memory table, normalizing column values so
    the SQL written against f1.db behaves the same (e.g. results.position
    must be TEXT, '1'/'2'/... , like the database)."""
    frame = df.copy()
    if name == "results" and "position" in frame.columns:
        def _pos(v: Any) -> Any:
            if v is None or (isinstance(v, float) and v != v):  # NaN guard
                return None
            try:
                return str(int(v))
            except (TypeError, ValueError):
                return None
        frame["position"] = frame["position"].apply(_pos)
    frame.to_sql(name, con, index=False, if_exists="replace")


@lru_cache(maxsize=1)
def _build_csv_conn() -> sqlite3.Connection:
    global _CSV_CONN, _CSV_MODE
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    tables = load_kaggle_all()
    for name, df in tables.items():
        _cs_to_conn(df, con, name)
    _CSV_CONN = con
    _CSV_MODE = True
    return con


def _is_csv_conn(con: sqlite3.Connection) -> bool:
    return _CSV_CONN is not None and con is _CSV_CONN


def _conn() -> sqlite3.Connection:
    if db_available():
        return connect_sqlite()
    return _build_csv_conn()


def _actionable_missing_table(table: str) -> DataNotFoundError:
    return DataNotFoundError(
        f"Query needs table {table!r}, which only exists in f1.db "
        "(telemetry data is not part of the tracked CSV snapshot).\n\n"
        "Place f1.db at dataset/huggingface/f1.db (see dataset_overview.txt) or run "
        "`f1-analytics data-status` for help, then retry."
    )


def query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a SELECT. Dict params are positional by insertion order."""
    con = _conn()
    csv_mode = _is_csv_conn(con)
    close_after = not csv_mode
    try:
        if params:
            params = tuple(params.values())
        return pd.read_sql(sql, con, params=params or None)
    except sqlite3.OperationalError as exc:
        if csv_mode:
            m = _MISSING_TABLE_RE.search(str(exc))
            if m and m.group(1) in _DB_ONLY_TABLES:
                raise _actionable_missing_table(m.group(1)) from exc
        raise
    finally:
        if close_after:
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


def lap_pace_race(race_id: int) -> pd.DataFrame:
    """Clean per-lap pacing/tyre data for one race (fastf1_laps, Race session).

    f1.db only - raises DataNotFoundError under the CSV fallback.
    """
    return query(
        """
        SELECT l.driverId, d.code, d.forename || ' ' || d.surname AS driver,
               c.name AS constructor, l.lap, l.time_sec, l.s1, l.s2, l.s3,
               l.compound, l.tyre_life, l.stint, l.position, l.track_status,
               l.speed_fl, l.speed_i1, l.speed_i2, l.speed_trap
        FROM fastf1_laps l
        JOIN drivers d ON d.driverId = l.driverId
        JOIN results res ON res.raceId = l.raceId AND res.driverId = l.driverId
        JOIN constructors c ON c.constructorId = res.constructorId
        WHERE l.raceId = ?
          AND l.session = 'Race'
          AND l.is_accurate = 1
        ORDER BY l.driverId, l.lap
        """,
        {"race_id": race_id},
    )