"""Flask application factory for the RACELAB F1 Analytics API."""

from __future__ import annotations

from flask import Flask, jsonify

from .config import Config
from .errors import register_error_handlers
from .api import register_blueprints


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    from flask_cors import CORS
    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}})

    register_blueprints(app)
    register_error_handlers(app)

    @app.get("/")
    def index():
        return jsonify({
            "name": Config.API_TITLE,
            "status": "ok",
            "api": Config.API_PREFIX,
            "endpoints": [
                "/api/health", "/api/data-source", "/api/data/status",
                "/api/data/validations", "/api/calendar", "/api/races/<id>/results",
                "/api/drivers", "/api/drivers/<id>", "/api/drivers/head-to-head",
                "/api/constructors", "/api/constructors/pit-stops",
                "/api/constructors/<year>/points", "/api/circuits",
                "/api/circuits/<ref>/winners", "/api/circuits/pace",
                "/api/coach/laps", "/api/coach/race", "/api/coach/live",
                "/api/models/status", "/api/models/train", "/api/models/train/status",
                "/api/predict", "/api/assistant/ask", "/api/live/providers",
                "/api/live/session", "/api/live/snapshot", "/api/live/refresh",
                "/api/live/save-snapshot", "/api/live/replays",
            ],
        })

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app
