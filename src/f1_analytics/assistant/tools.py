"""Read-only tool whitelist used by the Race Assistant (Phase 11)."""

from __future__ import annotations

import json
import sqlite3
import traceback
from typing import Any, Callable

import pandas as pd

from .. import config
from ..analytics import (
    circuit_analytics_table,
    constructor_summary_table,
    driver_summary_table,
)
from ..data import DataNotFoundError, open_f1_db

# SELECT-only execution is enforced twice: parser + a second value-level check.
_READ_ONLY_RE = r"^\s*(SELECT|WITH|EXPLAIN)\b"

TOOL_NAMES = (
    "sql_query", "driver_analytics", "constructor_analytics",
    "circuit_analytics", "data_coverage",
)


def _result_payload(success: bool, value: Any) -> dict[str, Any]:
    return {"success": success, "value": value}


def tool_driver_analytics(name: str | None = None) -> dict[str, Any]:
    try:
        df = driver_summary_table()
        if name:
            df = df[df["driver"].str.contains(name, case=False, na=False)]
        return _result_payload(True, df.head(20).to_dict(orient="records"))
    except Exception as exc:  # noqa: BLE001
        return _result_payload(False, str(exc))


def tool_constructor_analytics() -> dict[str, Any]:
    try:
        return _result_payload(True, constructor_summary_table().head(20).to_dict(orient="records"))
    except Exception as exc:  # noqa: BLE001
        return _result_payload(False, str(exc))


def tool_circuit_analytics(circuit: str | None = None) -> dict[str, Any]:
    try:
        table = circuit_analytics_table()
        if circuit:
            table = table[table["circuitRef"].astype(str).str.contains(circuit, case=False, na=False)]
        return _result_payload(True, table.head(20).to_dict(orient="records"))
    except Exception as exc:  # noqa: BLE001
        return _result_payload(False, str(exc))


def tool_sql_query(query: str, safety_live: Any | None = None) -> dict[str, Any]:
    """Run a SELECT-only query over f1.db. Must not write."""
    if not isinstance(query, str):
        return _result_payload(False, "query must be a string")
    import re
    match = re.match(_READ_ONLY_RE, query.strip(), re.IGNORECASE)
    if not match:
        return _result_payload(False, "only SELECT queries allowed (read-only whitelist)")
    lower = query.lower()
    for bad in ("insert", "update", "delete", "drop", "create", "alter", "pragma", "attach"):
        if bad in lower:
            return _result_payload(False, f"blocked keyword: {bad}")
    try:
        con = open_f1_db(purpose="the race assistant SQL tool")
        df = pd.read_sql(query, con, params={})
        con.close()
        return _result_payload(True, df.head(50).to_dict(orient="records"))
    except DataNotFoundError as exc:
        return _result_payload(False, str(exc))
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        return _result_payload(False, f"sql error: {exc}")
    except Exception as exc:  # noqa: BLE001
        return _result_payload(False, f"unexpected: {exc}")


def tool_data_coverage() -> dict[str, Any]:
    from ..preprocessing import DB_ROW_COUNTS
    coverage = {
        "f1.db_tables": len(DB_ROW_COUNTS),
        "csv_end_year": 2024,
        "lap_data_starts": 2018,
        "live_history_start": 2023,
        "tracks_mapped": 24,
        "model_holdout": "2026 partial",
        "openf1_url": config.OPENF1_BASE_URL,
    }
    return _result_payload(True, coverage)


def tool_live_status(snapshot) -> dict[str, Any]:
    if snapshot is None or snapshot.is_empty:
        return _result_payload(True, {"is_live": False, "message": "no live feed"})
    lb = snapshot.leaderboard
    return _result_payload(True, {
        "source": snapshot.source,
        "fetched_at": snapshot.fetched_at,
        "is_live": snapshot.is_live,
        "session": snapshot.session.get("session_name"),
        "leaderboard": lb.head(10).to_dict(orient="records"),
        "warnings": snapshot.warnings[:3],
    })


def tool_live_racecontrol(snapshot) -> dict[str, Any]:
    if snapshot is None:
        return _result_payload(True, {"message": "no live feed"})
    rc = snapshot.race_control
    if rc.empty:
        return _result_payload(True, {"message": "no race control messages", "is_empty": True})
    return _result_payload(True, {
        "rows": rc.tail(10).to_dict(orient="records"),
        "count": int(len(rc)),
        "source": snapshot.source,
        "fetched_at": snapshot.fetched_at,
    })


def tool_coach_report(snapshot=None, driver_id: int | None = None) -> dict[str, Any]:
    from ..coach import coach_laps, live_coach_from_snapshot
    try:
        if driver_id is not None:
            report = coach_laps(driver_id=int(driver_id))
            return _result_payload(True, {
                "driver": report.driver,
                "findings": [f.__dict__ for f in report.findings],
                "warnings": report.warnings,
            })
        if snapshot is not None:
            report = live_coach_from_snapshot(snapshot)
            return _result_payload(True, {
                "driver": report.driver,
                "findings": [f.__dict__ for f in report.findings],
                "warnings": report.warnings,
            })
        return _result_payload(False, "coach_report requires driver_id or snapshot")
    except Exception as exc:  # noqa: BLE001
        return _result_payload(False, f"coach error: {exc}")


def tool_predict_race(artifact=None, driver_row: dict | None = None) -> dict[str, Any]:
    """Optional: run a stored model artifact on one driver row."""
    try:
        import pandas as pd
        from ..models import predict_df
        if artifact is None or driver_row is None:
            return _result_payload(False, "predict_race needs a model artifact and driver row")
        df = pd.DataFrame([driver_row])
        out = predict_df(artifact, df)
        return _result_payload(True, out.iloc[0].to_dict())
    except Exception as exc:  # noqa: BLE001
        return _result_payload(False, f"predict error: {exc}")


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "sql_query": tool_sql_query,
    "driver_analytics": tool_driver_analytics,
    "constructor_analytics": tool_constructor_analytics,
    "circuit_analytics": tool_circuit_analytics,
    "data_coverage": tool_data_coverage,
    "live_status": tool_live_status,
    "live_racecontrol": tool_live_racecontrol,
    "coach_report": tool_coach_report,
}


def describe_tools() -> list[dict[str, str]]:
    return [
        {"name": n,
         "description": f.__doc__ or ""}
        for n, f in TOOLS.items()
    ]