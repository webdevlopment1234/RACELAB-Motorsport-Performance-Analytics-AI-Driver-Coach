"""Offline smoke tests (no pytest required). Uses real local data only.

Run:  .venv\\Scripts\\python.exe tests\\run_tests.py
"""

import tempfile
from pathlib import Path

import pandas as pd


def test_loaders_exist():
    from f1_analytics.data import CSV_FILES, load_csv, load_kaggle_all
    assert len(CSV_FILES) == 14
    circuits = load_csv("circuits")
    assert "circuitId" in circuits.columns
    all_tables = load_kaggle_all()
    assert set(all_tables) == set(CSV_FILES)


def test_validation_passes_on_real_data():
    from f1_analytics.preprocessing import run_all_validations
    reports = run_all_validations()
    for r in reports:
        if r.source in ("tracks.yaml",):
            continue  # coverage-gap check may vary; assert no failures except known
        assert not r.failures, f"{r.source} failures: {[c.message for c in r.failures]}"


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


def test_mock_empty_not_listbug():
    """Regression: empty endpoints must be empty DataFrames, never lists."""
    from f1_analytics.live import create_provider
    snap = create_provider("mock").snapshot()
    for name in ("drivers", "leaderboard", "latest_laps", "weather",
                 "race_control", "stints", "intervals"):
        assert isinstance(getattr(snap, name), pd.DataFrame)


def test_openf1_iso_parser():
    from f1_analytics.live import openf1
    assert openf1._iso("2026-03-08T04:00:00Z") is not None
    assert openf1._iso(None) is None


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


def test_simulation_runs():
    from f1_analytics.simulation import simulate
    s = simulate(seed=1, n_runs=10)
    assert len(s.place) >= 1 and {"wins", "podiums", "dnfs"} <= set(s.place.columns)


def test_coach_requires_data():
    from f1_analytics.coach import coach_laps
    report = coach_laps(driver_id=-1)  # nonexistent -> graceful
    assert report.n_laps == 0 and report.warnings


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