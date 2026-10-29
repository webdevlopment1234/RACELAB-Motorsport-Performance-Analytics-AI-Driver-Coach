"""Blueprint registration."""

from __future__ import annotations

from .meta import bp as meta_bp
from .analytics import bp as analytics_bp
from .predictions import bp as predictions_bp
from .coach import bp as coach_bp
from .assistant import bp as assistant_bp
from .live import bp as live_bp
from .health import bp as health_bp


def register_blueprints(app) -> None:
    app.register_blueprint(meta_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(predictions_bp)
    app.register_blueprint(coach_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(health_bp)
