"""Live timing providers (Phase 7).

All providers implement LiveProvider and return snapshots whose state
mirrors f1.db schemas. Default source is OpenF1 (free, no key, 2023+
history). MockProvider is deterministic for offline development/tests.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd


@dataclass
class LiveSnapshot:
    source: str
    fetched_at: str  # ISO-8601 UTC
    session: dict = field(default_factory=dict)
    is_live: bool = False
    is_empty: bool = False
    drivers: pd.DataFrame = field(default_factory=pd.DataFrame)
    leaderboard: pd.DataFrame = field(default_factory=pd.DataFrame)
    latest_laps: pd.DataFrame = field(default_factory=pd.DataFrame)
    weather: pd.DataFrame = field(default_factory=pd.DataFrame)
    race_control: pd.DataFrame = field(default_factory=pd.DataFrame)
    stints: pd.DataFrame = field(default_factory=pd.DataFrame)
    intervals: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)

    DFRAME_FIELDS = ("drivers", "leaderboard", "latest_laps", "weather",
                     "race_control", "stints", "intervals")

    def __post_init__(self) -> None:
        for name in self.DFRAME_FIELDS:
            df = getattr(self, name)
            if df is None:
                setattr(self, name, pd.DataFrame())

    @property
    def age_seconds(self) -> float:
        now = datetime.now(timezone.utc)
        fetched = datetime.fromisoformat(self.fetched_at)
        return max(0.0, (now - fetched).total_seconds())

    def to_dict(self) -> dict:
        out = {
            "source": self.source,
            "fetched_at": self.fetched_at,
            "session": self.session,
            "is_live": self.is_live,
            "is_empty": self.is_empty,
            "warnings": self.warnings,
        }
        for name in self.DFRAME_FIELDS:
            out[name] = getattr(self, name).to_dict(orient="records")
        return out


class LiveProvider(ABC):
    """Interface: build monitors heartbeat + refresh; snapshot() is the product."""

    name = "base"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: LiveSnapshot | None = None
        self._last_error: str | None = None
        self._heartbeat: datetime | None = None

    @abstractmethod
    def refresh(self) -> LiveSnapshot:
        raise NotImplementedError

    def snapshot(self) -> LiveSnapshot:
        with self._lock:
            if self._snapshot is None:
                self._snapshot = self.refresh()
            return self._snapshot

    def update(self) -> LiveSnapshot:
        with self._lock:
            self._snapshot = self.refresh()
            self._heartbeat = datetime.now(timezone.utc)
            return self._snapshot

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def is_stale(self, max_age: float = 15.0) -> bool:
        """Stale when heartbeat older than max_age OR no snapshot at all."""
        if self._snapshot is None:
            return True
        return self._snapshot.age_seconds > max_age


def create_provider(name: str, **kwargs) -> LiveProvider:
    if name == "mock":
        from .providers import MockProvider
        return MockProvider(**kwargs)
    if name == "openf1":
        from .openf1 import OpenF1LiveProvider
        return OpenF1LiveProvider(**kwargs)
    if name == "replay":
        from .replay import ReplayProvider
        return ReplayProvider(**kwargs)
    raise ValueError(f"Unknown live provider: {name!r}")