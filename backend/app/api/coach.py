"""Coach endpoints: laps-based and race-based reports."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from f1_analytics.coach.report import coach_laps, coach_race

from ..errors import ApiError
from ..services.reports import report_dict

bp = Blueprint("coach", __name__)


@bp.get("/api/coach/laps")
def coach_laps_route():
    driver_id = request.args.get("driver_id", type=int)
    if not driver_id:
        raise ApiError("query param 'driver_id' is required", 400)
    session = request.args.get("session", "Race")
    year_min = request.args.get("year_min", 2018, type=int)
    year_max = request.args.get("year_max", 2026, type=int)
    return jsonify(report_dict(coach_laps(driver_id, session, year_min, year_max)))


@bp.get("/api/coach/race")
def coach_race_route():
    race_id = request.args.get("race_id", type=int)
    driver_id = request.args.get("driver_id", type=int)
    if not race_id or not driver_id:
        raise ApiError("query params 'race_id' and 'driver_id' are required", 400)
    return jsonify(report_dict(coach_race(race_id, driver_id)))
