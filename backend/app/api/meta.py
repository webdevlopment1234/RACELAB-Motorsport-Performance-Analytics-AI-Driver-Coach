"""Meta endpoints: data source summary."""

from __future__ import annotations

from flask import Blueprint, jsonify

from f1_analytics.database import data_source

bp = Blueprint("meta", __name__)


@bp.get("/api/data-source")
def data_source_summary():
    return jsonify(data_source())
