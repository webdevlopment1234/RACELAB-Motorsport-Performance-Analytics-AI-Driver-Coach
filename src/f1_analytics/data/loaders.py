"""Data loaders for CSV, Parquet, SQLite, and YAML."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .. import config

CSV_FILES = {
    "circuits": "circuits.csv",
    "constructor_results": "constructor_results.csv",
    "constructor_standings": "constructor_standings.csv",
    "constructors": "constructors.csv",
    "driver_standings": "driver_standings.csv",
    "drivers": "drivers.csv",
    "lap_times": "lap_times.csv",
    "pit_stops": "pit_stops.csv",
    "qualifying": "qualifying.csv",
    "races": "races.csv",
    "results": "results.csv",
    "seasons": "seasons.csv",
    "sprint_results": "sprint_results.csv",
    "status": "status.csv",
}


class DataNotFoundError(FileNotFoundError):
    pass


def load_csv(name: str, dirpath: Path | None = None) -> pd.DataFrame:
    """Load a Kaggle-style CSV by canonical name."""
    if name not in CSV_FILES:
        raise ValueError(f"Unknown CSV dataset {name!r}")
    path = (dirpath or config.KAGGLE_DIR) / CSV_FILES[name]
    if not path.exists():
        raise DataNotFoundError(f"Missing data file: {path}")
    return pd.read_csv(path, low_memory=False)


def load_kaggle_all(dirpath: Path | None = None) -> dict[str, pd.DataFrame]:
    """Load all 14 CSV files as a dict keyed by canonical name."""
    return {name: load_csv(name, dirpath) for name in CSV_FILES}


def load_parquet(name: str, dirpath: Path | None = None) -> pd.DataFrame:
    """Load a parquet file by canonical name (training_dataset, driver_profiles)."""
    path = (dirpath or config.HUGGINGFACE_DIR) / name
    if not path.exists():
        raise DataNotFoundError(f"Missing data file: {path}")
    return pd.read_parquet(path)


def load_training_dataset(dirpath: Path | None = None) -> pd.DataFrame:
    return load_parquet("training_dataset.parquet", dirpath)


def load_driver_profiles(dirpath: Path | None = None) -> pd.DataFrame:
    return load_parquet("driver_profiles.parquet", dirpath)


def connect_sqlite(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.F1_DB_PATH
    if not path.exists():
        raise DataNotFoundError(f"Missing database: {path}")
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def sqlite_tables(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def table_schema(con: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    """Return [(column_name, type)...] for a table."""
    rows = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [(r["name"], r["type"]) for r in rows]


def load_table(con: sqlite3.Connection, table: str) -> pd.DataFrame:
    if table not in sqlite_tables(con):
        raise ValueError(f"Unknown table {table!r}")
    return pd.read_sql(f'SELECT * FROM "{table}"', con)


def load_tracks(dirpath: Path | None = None) -> dict[str, dict[str, Any]]:
    path = (dirpath or config.HUGGINGFACE_DIR) / "tracks.yaml"
    if not path.exists():
        raise DataNotFoundError(f"Missing data file: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "tracks" not in data:
        raise ValueError("tracks.yaml must contain a top-level 'tracks' key")
    return data["tracks"]


def tracks_frame(dirpath: Path | None = None) -> pd.DataFrame:
    """tracks.yaml as a DataFrame indexed by circuitRef."""
    tracks = load_tracks(dirpath)
    df = pd.DataFrame(tracks).T
    df.index.name = "circuitRef"
    return df.reset_index()