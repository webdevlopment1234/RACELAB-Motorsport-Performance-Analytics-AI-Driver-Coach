"""Thread-safe registry for the active live timing session."""

from __future__ import annotations

import threading

from f1_analytics.live import LiveProvider, create_provider


class LiveSessionError(Exception):
    pass


class LiveSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._provider: LiveProvider | None = None
        self._name: str | None = None

    def start(self, name: str) -> dict:
        with self._lock:
            provider = create_provider(name)
            provider.update()
            self._provider = provider
            self._name = name
            return {"provider": name, "started": True}

    def stop(self) -> dict:
        with self._lock:
            self._provider = None
            self._name = None
            return {"provider": None, "started": False}

    def provider(self) -> LiveProvider | None:
        with self._lock:
            return self._provider

    def name(self) -> str | None:
        with self._lock:
            return self._name

    def snapshot_dict(self) -> dict | None:
        provider = self.provider()
        if provider is None:
            return None
        return provider.snapshot().to_dict()


session = LiveSession()
