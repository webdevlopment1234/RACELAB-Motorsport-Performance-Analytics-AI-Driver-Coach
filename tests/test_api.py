"""Flask API smoke tests (no dataset required)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from app import create_app


def _client():
    return create_app().test_client()


def test_health():
    r = _client().get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_live_providers_and_replays():
    c = _client()
    r = c.get("/api/live/providers")
    assert r.status_code == 200
    assert set(r.get_json()["providers"]) >= {"openf1", "mock", "replay"}
    r2 = c.get("/api/live/replays")
    assert r2.status_code == 200
    assert "count" in r2.get_json()


def test_snapshot_guard_without_session():
    c = _client()
    c.delete("/api/live/session")
    r = c.get("/api/live/snapshot")
    assert r.status_code == 409


def test_live_session_and_snapshot():
    c = _client()
    r = c.post("/api/live/session", json={"provider": "mock"})
    assert r.status_code == 200
    snap = c.get("/api/live/snapshot")
    assert snap.status_code == 200
    data = snap.get_json()
    assert data["source"] == "mock"
    assert isinstance(data["leaderboard"], list)
    r2 = c.get("/api/live/preview", query_string={"provider": "mock"})
    assert r2.status_code == 200
    c.delete("/api/live/session")


def test_unknown_provider_rejected():
    r = _client().post("/api/live/session", json={"provider": "nope"})
    assert r.status_code == 400


def test_data_status_assets_shape():
    r = _client().get("/api/data/status")
    assert r.status_code == 200
    body = r.get_json()
    assert "assets" in body and "ok" in body


def test_analytics_tables_or_service_error():
    c = _client()
    r = c.get("/api/calendar")
    if r.status_code == 200:
        body = r.get_json()
        assert {"count", "columns", "rows"} <= set(body)
        dr = c.get("/api/drivers")
        assert dr.status_code == 200
    else:
        assert r.status_code == 503


def test_models_status_shape():
    r = _client().get("/api/models/status")
    assert r.status_code == 200
    body = r.get_json()
    assert "ok" in body and "models" in body


def test_predict_requires_row():
    r = _client().post("/api/predict", json={"task": "finish", "row": {}})
    assert r.status_code == 400
