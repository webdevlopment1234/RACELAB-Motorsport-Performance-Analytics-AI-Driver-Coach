"""Validation and drift reporting for all data sources."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..data import (
    CSV_FILES,
    connect_sqlite,
    load_kaggle_all,
    load_training_dataset,
    load_tracks,
    sqlite_tables,
)
from .schemas import (
    CSV_ROW_COUNTS,
    CSV_SCHEMAS,
    DB_ROW_COUNTS,
    DRIVER_PROFILES_COLUMNS,
    TRAINING_COLUMNS,
    TRAINING_NULL_PROFILE,
    TRACKS_KEYS,
    TRACKS_REQUIRED_FIELDS,
)


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    message: str


@dataclass
class ValidationReport:
    source: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, message: str, warn: bool = False) -> None:
        status = "ok" if ok else ("warn" if warn else "fail")
        self.checks.append(Check(name, status, message))

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.status == "warn"]

    def summary(self) -> str:
        return (
            f"{self.source}: {len(self.checks)} checks, "
            f"{len(self.failures)} failures, {len(self.warnings)} warnings"
        )

    def to_rows(self) -> list[dict[str, str]]:
        return [{"check": c.name, "status": c.status, "message": c.message} for c in self.checks]


def _expect_dtypes(df: pd.DataFrame, schema: dict[str, str]) -> list[str]:
    problems = []
    for col, kind in schema.items():
        if col not in df.columns:
            problems.append(f"missing column {col}")
            continue
        if kind == "int":
            nonnull = df[col].dropna()
            if nonnull.dtype.kind not in "iu" and not (
                nonnull.dtype.kind == "f" and (nonnull == nonnull.astype("int64")).all()
            ):
                problems.append(f"column {col} not integer")
    return problems


def validate_csv_all() -> ValidationReport:
    report = ValidationReport("kaggle_csv")
    try:
        tables = load_kaggle_all()
    except Exception as exc:  # noqa: BLE001
        report.add("load_all", False, f"failed to load CSVs: {exc}")
        return report

    for name in CSV_FILES:
        df = tables[name]
        schema = CSV_SCHEMAS[name]
        problems = _expect_dtypes(df, schema)
        report.add(f"{name}.columns", not problems, "; ".join(problems) or "columns/types ok")
        expected = CSV_ROW_COUNTS[name]
        actual = len(df)
        warn = expected is not None
        report.add(f"{name}.rows", actual == expected, f"rows {actual} (expected {expected})", warn=warn)
        dup_cols = {
            "races": "raceId", "drivers": "driverId", "circuits": "circuitId",
            "seasons": "year", "status": "statusId", "constructors": "constructorId",
        }
        if name in dup_cols:
            col = dup_cols[name]
            dups = df[col].duplicated().sum()
            report.add(f"{name}.pk", dups == 0, f"duplicate {col}: {dups}")

    # FK sanity: results -> races, results -> drivers
    races = tables["races"]
    results = tables["results"]
    orphans = results[~results["raceId"].isin(races["raceId"])]["raceId"].nunique()
    report.add("results.raceId_fk", orphans == 0, f"orphaned raceId values: {orphans}")
    drivers = tables["drivers"]
    orphans = results[~results["driverId"].isin(drivers["driverId"])]["driverId"].nunique()
    report.add("results.driverId_fk", orphans == 0, f"orphaned driverId values: {orphans}")
    return report


def validate_db() -> ValidationReport:
    report = ValidationReport("f1.db")
    try:
        con = connect_sqlite()
    except Exception as exc:  # noqa: BLE001
        report.add("connect", False, f"could not open f1.db: {exc}")
        return report
    with con:
        tables = sqlite_tables(con)
        for name, expected in DB_ROW_COUNTS.items():
            if name not in tables:
                report.add(f"{name}.present", False, "table missing")
                continue
            n = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            report.add(f"{name}.rows", n == expected, f"rows {n} (expected {expected})", warn=True)
    # ranges
    races = pd.read_sql("SELECT MIN(year) lo, MAX(year) hi, COUNT(*) n FROM races", con)
    report.add(
        "races.coverage",
        races.loc[0, "lo"] == 1950 and races.loc[0, "hi"] >= 2026,
        f"races {races.loc[0,'lo']}-{races.loc[0,'hi']} ({races.loc[0,'n']})",
    )
    laps = pd.read_sql(
        "SELECT MIN(r.year) lo, MAX(r.year) hi FROM fastf1_laps l "
        "JOIN races r ON l.raceId = r.raceId",
        con,
    )
    report.add(
        "fastf1_laps.range",
        laps.loc[0, "lo"] == 2018,
        f"fastf1_laps {laps.loc[0,'lo']}-{laps.loc[0,'hi']} (must start 2018)",
    )
    con.close()
    return report


def validate_training_dataset() -> ValidationReport:
    report = ValidationReport("training_dataset.parquet")
    try:
        df = load_training_dataset()
    except Exception as exc:  # noqa: BLE001
        report.add("load", False, f"failed to load: {exc}")
        return report

    report.add("shape", df.shape == (5094, 31), f"shape {df.shape} (expected 5094 x 31)")
    missing = [c for c in TRAINING_COLUMNS if c not in df.columns]
    report.add("columns", not missing, f"missing columns: {missing}")
    for t in ["finish", "is_dnf", "is_winner", "is_podium"]:
        nulls = df[t].isna().sum()
        report.add(f"target.{t}", nulls == 0, f"{t} nulls: {nulls}")
    if "year" in df:
        lo, hi = int(df["year"].min()), int(df["year"].max())
        report.add("year_range", (lo, hi) == (2014, 2026), f"years {lo}-{hi}")

    # Null-profile drift (tolerance +-0.05 on missing fraction)
    n = len(df)
    for col, expected in TRAINING_NULL_PROFILE.items():
        if col not in df.columns:
            continue
        frac = df[col].isna().mean()
        ok = abs(frac - expected) < 0.05
        report.add(f"nulls.{col}", ok,
                   f"{frac:.3f} null (expected {expected:.3f})", warn=not ok)

    # Derived feature present
    report.add(
        "grid_position_sq",
        "grid_position_sq" in df.columns,
        "derived grid_position_sq present",
    )

    # 2026 partial season exists
    counts = df.groupby("year").size() if "year" in df else pd.Series(dtype=int)
    y2026 = int(counts.get(2026, 0)) if counts.size else 0
    report.add("year.2026_holdout", 0 < y2026 < 200, f"2026 rows: {y2026} (holdout)")
    return report


def validate_tracks() -> ValidationReport:
    report = ValidationReport("tracks.yaml")
    try:
        tracks = load_tracks()
    except Exception as exc:  # noqa: BLE001
        report.add("load", False, f"failed to load: {exc}")
        return report

    missing_keys = [k for k in TRACKS_KEYS if k not in tracks]
    report.add("keys.coverage", not missing_keys, f"missing keys: {missing_keys or 'none'}")
    bad = []
    for key, entry in tracks.items():
        missing_fields = [f for f in TRACKS_REQUIRED_FIELDS if f not in entry]
        if missing_fields:
            bad.append(f"{key}: missing {missing_fields}")
    report.add("fields", not bad, "; ".join(bad) or "all entries have required fields")
    # normalized [0,1] ranges for a few fields (multipliers exempt)
    range_problems = []
    for key, entry in tracks.items():
        for f in ["overtaking_difficulty", "safety_car_probability",
                  "rain_probability", "qualifying_importance"]:
            v = entry.get(f)
            if v is not None and not (0.0 <= v <= 1.0):
                range_problems.append(f"{key}.{f}={v}")
    report.add("normalized_range", not range_problems, "; ".join(range_problems) or "ok")
    report.add("count", len(tracks) == 23, f"{len(tracks)} tracks")
    return report


def drift_report() -> ValidationReport:
    """CSV vs f1.db row-count parity. Known expected deltas are warn-level."""
    report = ValidationReport("csv_vs_db_drift")
    try:
        csv_tables = load_kaggle_all()
        con = connect_sqlite()
    except Exception as exc:  # noqa: BLE001
        report.add("load", False, f"failed: {exc}")
        return report

    with con:
        for name, csv_count in CSV_ROW_COUNTS.items():
            if name not in DB_ROW_COUNTS:
                continue
            db_count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            if db_count == csv_count:
                report.add(name, True, f"CSV == DB ({csv_count})")
            else:
                report.add(name, False,
                           f"CSV {csv_count} vs DB {db_count} (delta {db_count - csv_count})",
                           warn=True)
    # Races coverage difference (known)
    csv_range = (int(csv_tables["races"]["year"].min()), int(csv_tables["races"]["year"].max()))
    db_range = pd.read_sql("SELECT MIN(year) lo, MAX(year) hi FROM races", con)
    report.add(
        "races.range",
        csv_range == (1950, 2024) and (db_range.loc[0, "lo"], db_range.loc[0, "hi"]) == (1950, 2026),
        f"CSV races {csv_range} vs DB races {(int(db_range.loc[0,'lo']), int(db_range.loc[0,'hi']))}",
        warn=True,
    )
    con.close()
    return report


def run_all_validations() -> list[ValidationReport]:
    return [validate_csv_all(), validate_db(), validate_training_dataset(),
            validate_tracks(), drift_report()]


def validation_summary() -> list[dict[str, Any]]:
    rows = []
    for report in run_all_validations():
        rows.append({
            "source": report.source,
            "summary": report.summary(),
            "checks": report.to_rows(),
        })
    return rows