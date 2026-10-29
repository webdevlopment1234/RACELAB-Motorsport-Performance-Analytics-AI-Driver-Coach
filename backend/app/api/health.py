"""Data health endpoints: asset readiness + validation suite."""

from __future__ import annotations

from flask import Blueprint, jsonify

from f1_analytics.data import asset_status
from f1_analytics.data import DataNotFoundError
from f1_analytics.preprocessing import run_all_validations

from ..errors import ApiError

bp = Blueprint("health", __name__)


@bp.get("/api/data/status")
def data_status():
    rows = []
    for asset in asset_status().values():
        rows.append({"asset": asset.name, "ok": asset.ok, "path": str(asset.path),
                     "role": asset.role, "optional": asset.optional, "fix": asset.fix})
    missing = [r for r in rows if not r["ok"]]
    return jsonify({"assets": rows, "present": len(rows) - len(missing),
                    "missing": len(missing), "ok": not missing})


@bp.get("/api/data/validations")
def validations():
    reports = []
    failed = 0
    try:
        all_reports = run_all_validations()
    except DataNotFoundError as exc:
        raise ApiError(str(exc), status=503) from exc
    for report in all_reports:
        checks = [{"name": c.name, "status": c.status, "message": c.message}
                  for c in report.checks]
        failures = [c for c in checks if c["status"] == "fail"]
        failed += len(failures)
        reports.append({"source": report.source, "checks": checks,
                        "failures": len(failures), "warnings": len(
                            [c for c in checks if c["status"] == "warn"])})
    return jsonify({"reports": reports, "failing_checks": failed,
                    "ok": failed == 0})
