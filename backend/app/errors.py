"""JSON-safe exception handling for the API."""

from __future__ import annotations

import logging
import traceback

from flask import jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 500, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail

    def to_dict(self) -> dict:
        out = {"error": self.message, "status": self.status}
        if self.detail:
            out["detail"] = self.detail
        return out


def register_error_handlers(app) -> None:
    @app.errorhandler(ApiError)
    def on_api_error(err: ApiError):
        return jsonify(err.to_dict()), err.status

    @app.errorhandler(HTTPException)
    def on_http_error(err: HTTPException):
        return jsonify({"error": err.name, "status": err.code}), err.code or 500

    @app.errorhandler(Exception)
    def on_unexpected(err: Exception):
        log.error("unhandled error: %s\n%s", err, traceback.format_exc())
        return jsonify({"error": f"{type(err).__name__}: {err}", "status": 500}), 500
