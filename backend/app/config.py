"""Environment-driven configuration for the API."""

from __future__ import annotations

import os


def _origins() -> list[str]:
    raw = os.getenv("F1_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


class Config:
    API_TITLE = "RACELAB F1 Analytics API"
    API_PREFIX = "/api"
    CORS_ORIGINS = _origins()
    HOST = os.getenv("F1_API_HOST", "127.0.0.1")
    PORT = int(os.getenv("F1_API_PORT", "5000"))
