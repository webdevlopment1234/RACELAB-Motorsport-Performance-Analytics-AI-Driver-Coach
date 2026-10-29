"""Background model-training job with status polling."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from f1_analytics.models import train_all_years

_lock = threading.Lock()
_state: dict = {"status": "idle", "started_at": None, "finished_at": None,
                "tasks": {}, "error": None}


def _run() -> None:
    try:
        artifacts = train_all_years(save=True)
        result = {a.task: {"metrics": a.metrics, "split": a.split,
                           "seed": a.seed, "inputs": len(a.input_columns),
                           "path": str(a.path) if hasattr(a, "path") else None}
                  for a in artifacts}
        with _lock:
            _state.update(status="done", tasks=result,
                          finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:  # noqa: BLE001 - job status must capture failures
        with _lock:
            _state.update(status="error", error=str(exc),
                          finished_at=datetime.now(timezone.utc).isoformat())


def start_training() -> dict:
    with _lock:
        if _state["status"] == "running":
            return dict(_state)
        _state.update(status="running", error=None, tasks={},
                      started_at=datetime.now(timezone.utc).isoformat(),
                      finished_at=None)
    threading.Thread(target=_run, daemon=True).start()
    return dict(_state)


def job_status() -> dict:
    with _lock:
        return dict(_state)
