"""Live timing endpoints: session lifecycle + snapshot access."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from f1_analytics.data import DataNotFoundError
from f1_analytics.live import create_provider, latest_replay_path, list_replays, save_snapshot

from ..errors import ApiError
from ..services import live_state
from ..services.reports import report_dict

bp = Blueprint("live", __name__)

PROVIDERS = ("openf1", "mock", "replay")


@bp.get("/api/live/providers")
def providers():
    return jsonify({"providers": list(PROVIDERS), "active": live_state.session.name()})


@bp.get("/api/live/replays")
def replays():
    paths = list_replays()
    latest = latest_replay_path()
    return jsonify({
        "count": len(paths),
        "latest": str(latest) if latest else None,
        "replays": [str(p) for p in paths],
    })


@bp.post("/api/live/session")
def start_session():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("provider", "")).strip()
    if name not in PROVIDERS:
        raise ApiError(f"'provider' must be one of {PROVIDERS}", 400)
    try:
        result = live_state.session.start(name)
    except DataNotFoundError as exc:
        raise ApiError(str(exc), status=409) from exc
    except Exception as exc:  # noqa: BLE001
        raise ApiError(f"failed to start provider {name!r}: {exc}", 502) from exc
    return jsonify(result)


@bp.delete("/api/live/session")
def stop_session():
    return jsonify(live_state.session.stop())


@bp.get("/api/live/snapshot")
def snapshot():
    snap = live_state.session.snapshot_dict()
    if snap is None:
        raise ApiError("no active live session; POST /api/live/session first", 409)
    return jsonify(snap)


@bp.post("/api/live/refresh")
def refresh():
    provider = live_state.session.provider()
    if provider is None:
        raise ApiError("no active live session; POST /api/live/session first", 409)
    return jsonify(provider.update().to_dict())


@bp.post("/api/live/save-snapshot")
def save_replay():
    provider = live_state.session.provider()
    if provider is None:
        raise ApiError("no active live session to save", 409)
    path = save_snapshot(provider.snapshot())
    return jsonify({"saved": True, "path": str(path)})


@bp.get("/api/live/coach")
def live_coach():
    provider = live_state.session.provider()
    if provider is None:
        raise ApiError("no active live session", 409)
    from f1_analytics.coach.report import live_coach_from_snapshot
    return jsonify(report_dict(live_coach_from_snapshot(provider.snapshot())))


@bp.get("/api/live/preview")
def provider_preview():
    name = request.args.get("provider", "mock")
    if name not in PROVIDERS:
        raise ApiError(f"'provider' must be one of {PROVIDERS}", 400)
    try:
        provider = create_provider(name)
        return jsonify(provider.update().to_dict())
    except DataNotFoundError as exc:
        raise ApiError(str(exc), status=409) from exc
    except Exception as exc:  # noqa: BLE001
        raise ApiError(f"provider {name!r} failed: {exc}", 502) from exc
