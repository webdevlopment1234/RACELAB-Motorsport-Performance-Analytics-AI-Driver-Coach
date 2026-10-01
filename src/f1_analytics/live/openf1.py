"""OpenF1 live timing client (free, no key) + provider."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from .. import config
from .core import LiveProvider, LiveSnapshot


def _iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


@dataclass
class OpenF1Client:
    base_url: str = config.OPENF1_BASE_URL
    timeout: float = config.OPENF1_TIMEOUT
    max_retries: int = config.OPENF1_MAX_RETRIES
    session: requests.Session = field(default_factory=requests.Session)

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code in (404, 422):
                    return []  # best-effort endpoints; never crash
                resp.raise_for_status()
                return resp.json() if resp.status_code == 200 else []
            except requests.RequestException:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))
        return []

    def sessions(self, year: int | None = None) -> list[dict[str, Any]]:
        return self._get("sessions", {"year": year} if year else None)

    def drivers(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("drivers", {"session_key": session_key})

    def positions(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("position", {"session_key": session_key})

    def laps(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("laps", {"session_key": session_key})

    def intervals(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("intervals", {"session_key": session_key})

    def weather(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("weather", {"session_key": session_key})

    def race_control(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("race_control", {"session_key": session_key})

    def stints(self, session_key: int) -> list[dict[str, Any]]:
        return self._get("stints", {"session_key": session_key})


def _resolve_session(client: OpenF1Client, year: int | None = None,
                     session_key: int | None = None) -> dict[str, Any]:
    """Pick ongoing -> next upcoming -> most recent finished session."""
    if session_key is None:
        sessions = client.sessions(year)
        if not sessions:
            return {}
        parsed = []
        for s in sessions:
            start = _iso(s.get("date_start"))
            end = _iso(s.get("date_end"))
            parsed.append((start, end, s))
        now = datetime.now(timezone.utc)
        ongoing = [t for t in parsed if t[0] and t[1] and t[0] <= now < t[1]]
        if ongoing:
            return ongoing[0][2]
        upcoming = [t for t in parsed if t[0] and t[1] and t[0] > now]
        if upcoming:
            return min(upcoming, key=lambda t: t[0] or datetime.max)[2]
        finished = [t for t in parsed if t[1] and t[1] <= now]
        if finished:
            return max(finished, key=lambda t: t[1] or datetime.min)[2]
        return {}
    raise ValueError("session_key must be validated before resolution")


class OpenF1Provider(LiveProvider):
    """One snapshot per refresh; empty upcoming sessions yield empty DataFrames."""

    name = "openf1"
    REQUIRED = ("driver_number", "position", "time")

    def __init__(self, year: int | None = None, session_key: int | None = None,
                 client: OpenF1Client | None = None) -> None:
        super().__init__()
        self.client = client or OpenF1Client()
        self.session_key = session_key
        self.year = year
        self._session_meta: dict[str, Any] = {}
        self._init_warnings: list[str] = []
        if session_key is None:
            try:
                self.session_key = self._default_session(year, session_key)
            except requests.RequestException:
                # Offline / API down at startup: never crash the app. The
                # provider returns an empty, clearly-labeled snapshot instead.
                self.session_key = None
                self._init_warnings.append(
                    "OpenF1 API unreachable at startup - live feed unavailable"
                )

    def _default_session(self, year: int | None, session_key: int | None) -> int | None:
        meta = _resolve_session(self.client, year, session_key)
        self._session_meta = meta
        return meta.get("session_key")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _is_live(self, session: dict[str, Any]) -> bool:
        start = _iso(session.get("date_start"))
        end = _iso(session.get("date_end"))
        if not start or not end:
            return False
        now = datetime.now(timezone.utc)
        return start <= now < end

    def refresh(self) -> LiveSnapshot:
        if not self.session_key:
            return LiveSnapshot(source=self.name, fetched_at=self._now(),
                                is_empty=True,
                                warnings=self._init_warnings or
                                ["no active/upcoming session"])
        session = self.client._get("sessions", {"session_key": self.session_key})
        meta = session[0] if session else self._session_meta
        empty = not meta.get("date_start") or self._is_upcoming(meta)
        return LiveSnapshot(
            source=self.name,
            fetched_at=self._now(),
            session=meta,
            is_live=self._is_live(meta),
            is_empty=empty or len(meta) == 0,
            drivers=self._drivers(),
            leaderboard=self._leaderboard(),
            latest_laps=self._latest_laps(),
            weather=self._weather(),
            race_control=self._race_control(),
            stints=self._stints(),
            intervals=self._intervals(),
            warnings=self._warnings(meta) + self._init_warnings,
        )

    def _is_upcoming(self, session: dict[str, Any]) -> bool:
        start = _iso(session.get("date_start"))
        return start is not None and start > datetime.now(timezone.utc)

    def _fetch(self, fn) -> pd.DataFrame:
        try:
            data = fn(self.session_key)
        except requests.RequestException:
            return pd.DataFrame()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)

    def _drivers(self) -> pd.DataFrame:
        return self._fetch(self.client.drivers)

    def _leaderboard(self) -> pd.DataFrame:
        pos = self._fetch(self.client.positions)
        if pos.empty:
            return pd.DataFrame()
        pos = pos.sort_values("date", ascending=True)
        last = pos.drop_duplicates("driver_number", keep="last")
        cols = [c for c in self.REQUIRED if c in last.columns]
        return last[cols + [c for c in last.columns if c not in cols]] if last.shape[0] else pd.DataFrame()

    def _latest_laps(self) -> pd.DataFrame:
        laps = self._fetch(self.client.laps)
        if laps.empty:
            return pd.DataFrame()
        cols = ["driver_number", "lap_number", "lap_duration", "sector_1_time",
                "sector_2_time", "sector_3_time"]
        have = [c for c in cols if c in laps.columns]
        laps = laps[laps["lap_duration"].notna()].sort_values("lap_number", ascending=True)
        if laps.empty:
            return pd.DataFrame()
        return laps.drop_duplicates("driver_number", keep="last")[have] if have else pd.DataFrame()

    def _weather(self) -> pd.DataFrame:
        w = self._fetch(self.client.weather)
        if w.empty:
            return pd.DataFrame()
        w = w.sort_values("date", ascending=True)
        return w.drop_duplicates(subset=["session_key"], keep="last")

    def _race_control(self) -> pd.DataFrame:
        return self._fetch(self.client.race_control)

    def _stints(self) -> pd.DataFrame:
        return self._fetch(self.client.stints)

    def _intervals(self) -> pd.DataFrame:
        return self._fetch(self.client.intervals)

    def _warnings(self, session: dict[str, Any]) -> list[str]:
        w = []
        if not session:
            w.append("no session metadata")
        if self._is_upcoming(session):
            w.append("session has not started - showing no data yet")
        return w


class OpenF1LiveProvider(OpenF1Provider):
    name = "openf1"

    def __init__(self, poll_seconds: float = config.OPENF1_POLL_SECONDS,
                 year: int | None = None, session_key: int | None = None) -> None:
        super().__init__(year=year, session_key=session_key)
        self.poll_seconds = max(5.0, poll_seconds)

    def refresh(self) -> LiveSnapshot:
        return super().refresh()