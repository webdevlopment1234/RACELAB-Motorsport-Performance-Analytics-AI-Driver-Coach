"""DataFrame -> JSON-safe conversion helpers."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping

import numpy as np
import pandas as pd


def _scalar(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp,)):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def clean_value(value):
    if isinstance(value, Mapping):
        return {str(k): clean_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean_value(v) for v in value]
    return _scalar(value)


def records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return clean_value(df.to_dict(orient="records"))


def table(df: pd.DataFrame) -> dict:
    return clean_value({
        "count": int(len(df)),
        "columns": list(map(str, df.columns)),
        "rows": records(df),
    })


def ok(payload: dict | list | None):
    return {"ok": True, "data": payload}
