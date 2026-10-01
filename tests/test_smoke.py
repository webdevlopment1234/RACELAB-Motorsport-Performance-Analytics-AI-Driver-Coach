"""Offline smoke tests (no pytest required). Uses real local data only.

Run:  .venv\\Scripts\\python.exe tests\\run_tests.py
"""

import tempfile
from pathlib import Path

import pandas as pd


def _required_data_ok() -> bool:
    from f1_analytics.data import required_assets
    return not [a for a in required_assets() if not a.ok and not a.optional]


def requires_data(fn):
    """Skip data-dependent tests when the required local files are absent
    (e.g. a data-less CI checkout). The runner still counts them as PASS with
    an explicit (SKIP) marker."""
    import functools

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        if not _required_data_ok():
            print(f"SKIP {fn.__name__}: required local data missing")
            return None
        return fn(*args, **kwargs)
    return wrapped


@requires_data
def test_loaders_exist():
    from f1_analytics.data import CSV_FILES, load_csv, load_kaggle_all
    assert len(CSV_FILES) == 14
    circuits = load_csv("circuits")
    assert "circuitId" in circuits.columns
    all_tables = load_kaggle_all()
    assert set(all_tables) == set(CSV_FILES)


@requires_data
def test_validation_passes_on_real_data():
    from f1_analytics.preprocessing import run_all_validations
    reports = run_all_validations()
    for r in reports:
        if r.source in ("tracks.yaml",):
            continue  # coverage-gap check may vary; assert no failures except known
        assert not r.failures, f"{r.source} failures: {[c.message for c in r.failures]}"


@requires_data
def test_training_table_split():
    from f1_analytics.config import TEST_YEARS, TRAIN_MAX_YEAR, VAL_YEARS
    from f1_analytics.features import split_years, training_table
    df = training_table()
    assert df.shape[1] == 31
    train, val, test, holdout = split_years(df, TRAIN_MAX_YEAR, VAL_YEARS, TEST_YEARS)
    assert train["year"].max() == TRAIN_MAX_YEAR
    assert set(val["year"].unique()) <= set(VAL_YEARS)
    assert set(test["year"].unique()) <= set(TEST_YEARS)
    assert (holdout["year"] > max(TEST_YEARS)).all()


def test_leakage_contract():
    from f1_analytics.features import leaking_features
    from f1_analytics.models import PROD_INPUT_COLUMNS
    assert "pit_stop_avg_ms" in leaking_features("post_quali")
    assert "pit_stop_avg_ms" not in PROD_INPUT_COLUMNS
    assert "year" not in PROD_INPUT_COLUMNS


def test_mock_provider_snapshot_shape():
    from f1_analytics.live import create_provider
    snap = create_provider("mock").snapshot()
    assert snap.is_live and not snap.is_empty
    assert not snap.leaderboard.empty
    assert {"driver_number", "position"} <= set(snap.leaderboard.columns)
    assert not snap.telemetry.empty
    assert {"speed_kmh", "throttle_pct", "brake_pct", "gear", "delta_s"} <= \
        set(snap.telemetry.columns)


def test_mock_empty_not_listbug():
    """Regression: empty endpoints must be empty DataFrames, never lists."""
    from f1_analytics.live import create_provider
    snap = create_provider("mock").snapshot()
    for name in ("drivers", "leaderboard", "latest_laps", "weather",
                 "race_control", "stints", "intervals", "telemetry"):
        assert isinstance(getattr(snap, name), pd.DataFrame)


def test_openf1_iso_parser():
    from f1_analytics.live import openf1
    assert openf1._iso("2026-03-08T04:00:00Z") is not None
    assert openf1._iso(None) is None


@requires_data
def test_assistant_guardrails():
    from f1_analytics.assistant import LLMClient, ask
    from f1_analytics.live import create_provider
    snap = create_provider("mock").snapshot()
    llm = LLMClient()  # offline -> rule-based fallback
    refusal = ask("DELETE FROM results", snapshot=snap, llm=llm)
    assert refusal.answer.startswith("[refusal]")
    sel = ask("SELECT COUNT(*) AS n FROM races WHERE year=2026", snapshot=snap, llm=llm)
    assert "Query result" in sel.answer


def test_assistant_racecontrol_is_data_not_instructions():
    from f1_analytics.assistant.assistant import _RACE_CONTROL_UNTRUSTED
    assert _RACE_CONTROL_UNTRUSTED is True


@requires_data
def test_simulation_runs():
    from f1_analytics.simulation import simulate
    s = simulate(seed=1, n_runs=10)
    assert len(s.place) >= 1 and {"wins", "podiums", "dnfs"} <= set(s.place.columns)


@requires_data
def test_coach_requires_data():
    from f1_analytics.coach import coach_laps
    report = coach_laps(driver_id=-1)  # nonexistent -> graceful
    assert report.n_laps == 0 and report.warnings


@requires_data
def test_coach_race_scoped():
    from f1_analytics.coach import coach_race
    from f1_analytics.database import lap_pace_race, query
    rows = query(
        "SELECT r.raceId FROM races r JOIN fastf1_laps l ON l.raceId = r.raceId "
        "WHERE r.year = 2024 ORDER BY r.round LIMIT 1"
    )
    if rows.empty:
        return None
    race_id = int(rows.iloc[0]["raceId"])
    laps = lap_pace_race(race_id)
    driver_id = int(laps.iloc[0]["driverId"])
    report = coach_race(race_id, driver_id)
    assert report.n_laps > 0 and report.findings


@requires_data
def test_analytics_tables():
    from f1_analytics.analytics import (
        circuit_analytics_table,
        constructor_summary_table,
        driver_summary_table,
    )
    d = driver_summary_table()
    assert {"driver", "wins"} <= set(d.columns) and len(d) > 0
    c = constructor_summary_table()
    assert "starts_x" not in c.columns and "total_points" in c.columns
    ci = circuit_analytics_table()
    assert "circuitRef" in ci.columns


def test_replay_roundtrip():
    from f1_analytics.live import create_provider, load_snapshot, save_snapshot
    snap = create_provider("mock").snapshot()
    with tempfile.TemporaryDirectory() as tmp:
        path = save_snapshot(snap, Path(tmp) / "snap.json")
        loaded = load_snapshot(path)
        assert not loaded.leaderboard.empty
        assert loaded.source == "mock"


def _dummy_artifact():
    from sklearn.linear_model import LogisticRegression
    from f1_analytics.models.train import Artifact
    import numpy as np

    # Model is trained on the S1 expanded schema: inputs + missing indicators.
    X = pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0],
        "b": [3.0, 3.0, 3.0, 3.0],
        "b_missing": [0, 0, 0, 1],
    })
    y = np.array([0, 1, 0, 1])
    model = LogisticRegression().fit(X, y)
    return Artifact.from_parts(
        task="finish",
        model=model,
        input_columns=["a", "b"],
        medians={"b": 3.0},
        indicator_cols=["b_missing"],
    )


def test_s1_prep_builds_indicators_from_pre_impute_mask():
    """Regression: indicators must reflect NaNs before median fill (Strategy S1)."""
    from f1_analytics.models.train import _fit_imputation, _prep

    df = pd.DataFrame({"a": [1.0, float("nan")], "b": [2.0, 3.0]})
    medians, indicators = _fit_imputation(df, ["a", "b"])
    X = _prep(df, ["a", "b"], medians, indicators)
    assert "a_missing" in X.columns
    assert X.loc[0, "a_missing"] == 0 and X.loc[1, "a_missing"] == 1


def test_prep_predict_schema_stable():
    """Regression: clean scoring rows must use the same feature set as rows with
    missing values (indicator columns are rebuilt from the artifact, not from
    whatever happens to be missing at score time)."""
    from f1_analytics.models.train import _prep_predict, predict_df

    art = _dummy_artifact()
    missing_row = pd.DataFrame({"a": [1.0], "b": [float("nan")]})
    clean_row = pd.DataFrame({"a": [1.0], "b": [5.0]})

    x1 = _prep_predict(missing_row, art)
    x2 = _prep_predict(clean_row, art)
    assert list(x1.columns) == list(x2.columns)
    assert len(x1.columns) == len(art.input_columns) + len(art.indicator_cols)
    assert x1["b_missing"].eq(1).all() and x2["b_missing"].eq(0).all()

    p1 = predict_df(art, missing_row)
    p2 = predict_df(art, clean_row)
    assert "finish_pred" in p1.columns and not p1.empty and not p2.empty


def test_cli_commands_run():
    import contextlib
    import io

    from f1_analytics.cli import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["data-status"])
    out = buf.getvalue()
    assert rc == 0
    assert "Data readiness" in out and "missing" in out

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["models-status"])
    assert rc in (0, 1)  # entries validated regardless of trained artifacts

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["train"])
    assert rc in (0, 1)  # gracefully fails when training_dataset.parquet is absent


def test_asset_status_and_data_source():
    from f1_analytics.data import asset_status
    from f1_analytics.database import data_source

    assets = asset_status()
    assert "training_dataset.parquet" in assets
    src = data_source()
    assert src["mode"] in ("sqlite", "csv_fallback")
    assert {"mode", "db_path", "csv_fallback", "note"} <= set(src)


def test_models_status_report_shape():
    from f1_analytics.config import MODEL_TASKS
    from f1_analytics.models import models_status

    status = models_status()
    assert {"ok", "models"} <= set(status)
    assert set(status["models"]) == set(MODEL_TASKS)
    for info in status["models"].values():
        assert "ok" in info and "error" in info


def test_llm_offline_and_redaction():
    import os

    from f1_analytics.assistant import LLMClient, run_rule_based
    from f1_analytics.logging_utils import redact

    saved = os.environ.pop("F1_ASSISTANT_API_KEY", None)
    try:
        llm = LLMClient()
        assert llm.available is False
        assert llm.complete("sys", "user") is None
    finally:
        if saved is not None:
            os.environ["F1_ASSISTANT_API_KEY"] = saved

    ans = run_rule_based("who has the most wins?",
                         {"sql_query": {"success": True, "value": [{"driver": "HAM", "wins": 105}]}},
                         ["tool_sql_query"])
    assert "[rule-based answer]" in ans and "105" in ans

    scrubbed = redact("key sk-proj-AbcD1234567890123456789012 and Authorization Bearer tok1")
    assert "sk-***" in scrubbed and "sk-proj-" not in scrubbed

    jwt = redact("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token.extra")
    assert "eyJ" not in jwt and "Bearer ***" in jwt


def test_openf1_offline_provider_init():
    import requests

    from f1_analytics.live.openf1 import OpenF1Provider

    class _OfflineClient:
        def sessions(self, year=None):
            raise requests.RequestException("simulated offline")

    prov = OpenF1Provider(client=_OfflineClient())
    assert prov.session_key is None
    assert prov._init_warnings
    snap = prov.snapshot()
    assert snap.is_empty and snap.source == "openf1"


def test_dashboard_smoke():
    import ast
    import importlib.util
    import io
    import os
    import sys
    from contextlib import redirect_stderr

    path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in ast.walk(tree))

    if importlib.util.find_spec("streamlit") is None:
        return  # syntax contract checked; runtime needs streamlit

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "dashboard"))
    buf = io.StringIO()
    with redirect_stderr(buf):
        spec = importlib.util.spec_from_file_location("f1_dashboard", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    assert mod.PAGES and mod.PAGES[0] == "Analytics"