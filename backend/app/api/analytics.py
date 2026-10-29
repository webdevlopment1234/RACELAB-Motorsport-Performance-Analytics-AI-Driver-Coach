"""Analytics endpoints: drivers, constructors, circuits, calendar, results."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from f1_analytics.analytics import (
    circuit_analytics_table,
    circuit_historical_winners,
    circuit_pace,
    constructor_pit_stop_stats,
    constructor_season_points,
    constructor_summary_table,
    driver_head_to_head,
    driver_session_history,
    driver_summary_table,
)
from f1_analytics.data import DataNotFoundError
from f1_analytics.database import (
    drivers_with_laps,
    race_calendar,
    race_results,
    standings_driver,
)

from ..errors import ApiError
from ..json_utils import table

bp = Blueprint("analytics", __name__)


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DataNotFoundError as exc:
        raise ApiError(str(exc), status=503) from exc


@bp.get("/api/calendar")
def calendar():
    return jsonify(table(_guard(race_calendar)))


@bp.get("/api/races/<int:race_id>/results")
def race_results_for(race_id: int):
    return jsonify(table(_guard(race_results, race_id=race_id)))


@bp.get("/api/standings")
def standings():
    year = request.args.get("year", type=int)
    return jsonify(table(_guard(standings_driver, year)))


@bp.get("/api/drivers")
def drivers():
    return jsonify(table(_guard(driver_summary_table)))


@bp.get("/api/drivers/with-laps")
def drivers_with_laps_route():
    return jsonify(table(_guard(drivers_with_laps)))


@bp.get("/api/drivers/<int:driver_id>")
def driver_detail(driver_id: int):
    return jsonify(table(_guard(driver_session_history, driver_id)))


@bp.get("/api/drivers/head-to-head")
def head_to_head():
    a = request.args.get("a", type=int)
    b = request.args.get("b", type=int)
    if not a or not b:
        raise ApiError("query params 'a' and 'b' (driverIds) are required", 400)
    return jsonify(table(_guard(driver_head_to_head, a, b)))


@bp.get("/api/constructors")
def constructors():
    return jsonify(table(_guard(constructor_summary_table)))


@bp.get("/api/constructors/pit-stops")
def pit_stops():
    return jsonify(table(_guard(constructor_pit_stop_stats)))


@bp.get("/api/constructors/<int:year>/points")
def season_points(year: int):
    return jsonify(table(_guard(constructor_season_points, year)))


@bp.get("/api/circuits")
def circuits():
    return jsonify(table(_guard(circuit_analytics_table)))


@bp.get("/api/circuits/<string:circuit_ref>/winners")
def circuit_winners(circuit_ref: str):
    ref = None if circuit_ref == "all" else circuit_ref
    return jsonify(table(_guard(circuit_historical_winners, ref)))


@bp.get("/api/circuits/pace")
def circuit_pace_route():
    ref = request.args.get("circuit")
    session = request.args.get("session", "Race")
    return jsonify(table(_guard(circuit_pace, ref, session)))
