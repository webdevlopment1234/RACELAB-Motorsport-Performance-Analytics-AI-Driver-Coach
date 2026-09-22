"""Replay provider: load previously-recorded snapshots from disk."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .. import config
from .core import LiveProvider, LiveSnapshot


def save_snapshot(snapshot: LiveSnapshot, path: Path | None = None) -> Path:
    """Write a snapshot to dataset/live_replays as JSON (test/replay support)."""
    path = path or (config.LIVE_REPLAYS_DIR / f"{snapshot.fetched_at.replace(':', '-')}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> LiveSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"))
    frame_fields = LiveSnapshot.DFRAME_FIELDS
    kwargs: dict[str, Any] = {"source": data["source"], "fetched_at": data["fetched_at"]}
    for field in frame_fields:
        kwargs[field] = pd.DataFrame(data.get(field, []))
    return LiveSnapshot(**kwargs)


class ReplayProvider(LiveProvider):
    name = "replay"

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self._snapshot = load_snapshot(path)

    def refresh(self) -> LiveSnapshot:
        return self._snapshot