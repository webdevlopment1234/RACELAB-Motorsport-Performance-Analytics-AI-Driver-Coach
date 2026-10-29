"""Replay provider: load previously-recorded snapshots from disk."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .. import config
from ..data import DataNotFoundError
from .core import LiveProvider, LiveSnapshot


def save_snapshot(snapshot: LiveSnapshot, path: Path | None = None) -> Path:
    """Write a snapshot to dataset/live_replays as JSON (test/replay support)."""
    path = path or (config.LIVE_REPLAYS_DIR / f"{snapshot.fetched_at.replace(':', '-')}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return path


def list_replays(directory: Path | None = None) -> list[Path]:
    """Saved snapshot files, newest first (empty list when none exist)."""
    directory = Path(directory) if directory else config.LIVE_REPLAYS_DIR
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def latest_replay_path(directory: Path | None = None) -> Path | None:
    paths = list_replays(directory)
    return paths[0] if paths else None


def load_snapshot(path: Path | str) -> LiveSnapshot:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    frame_fields = LiveSnapshot.DFRAME_FIELDS
    kwargs: dict[str, Any] = {"source": data["source"], "fetched_at": data["fetched_at"]}
    for field in frame_fields:
        kwargs[field] = pd.DataFrame(data.get(field, []))
    return LiveSnapshot(**kwargs)


class ReplayProvider(LiveProvider):
    name = "replay"

    def __init__(self, path: Path | str | None = None) -> None:
        """Replay a saved snapshot JSON.

        With no path, the newest file in config.LIVE_REPLAYS_DIR is used; if
        none exist, the error is actionable (the dashboard shows it verbatim).
        """
        super().__init__()
        if path is None:
            path = latest_replay_path()
        if path is None:
            raise DataNotFoundError(
                "Provider 'replay' needs a saved snapshot, but "
                f"{config.LIVE_REPLAYS_DIR} contains none.\n\n"
                "Open the LIVE page, pick the openf1 or mock provider, press "
                "'Save snapshot as replay', then switch back to replay - "
                "or select a different provider.")
        self.path = Path(path)
        self._snapshot = load_snapshot(self.path)

    def refresh(self) -> LiveSnapshot:
        return self._snapshot