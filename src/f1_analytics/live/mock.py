"""Deterministic mock provider for offline development/tests."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .core import LiveProvider, LiveSnapshot

SEED_2026 = 2026
DRIVERS_2026 = [
    ("4", "VER", "Red Bull Racing", "#3671C6"),
    ("1", "NOR", "McLaren", "#FF8000"),
    ("81", "PIA", "McLaren", "#FF8000"),
    ("55", "SAI", "Ferrari", "#E8002D"),
    ("16", "LEC", "Ferrari", "#E8002D"),
    ("44", "HAM", "Mercedes", "#27F4D2"),
    ("63", "RUS", "Mercedes", "#27F4D2"),
    ("14", "ALO", "Aston Martin", "#229971"),
    ("18", "STR", "Aston Martin", "#229971"),
    ("6", "OCO", "Alpine", "#FF87BC"),
    ("10", "GAS", "Alpine", "#FF87BC"),
    ("24", "ZHO", "Sauber", "#52E252"),
    ("77", "BOT", "Sauber", "#52E252"),
    ("22", "TSU", "RB", "#6692FF"),
    ("30", "LAW", "RB", "#6692FF"),
    ("5", "BIA", "Williams", "#64C4FF"),
    ("23", "ALB", "Williams", "#64C4FF"),
    ("2", "HAD", "Haas", "#B6BABD"),
    ("31", "BEA", "Haas", "#B6BABD"),
    ("3", "AUD", "Audi", "#F50537"),
    ("7", "MUL", "Audi", "#F50537"),
    ("9", "CAD", "Cadillac", "#005AFF"),
]


class MockProvider(LiveProvider):
    """Synthetic 2026 Melbourne race snapshot; stable random_state."""

    name = "mock"

    def __init__(self, seed: int = SEED_2026) -> None:
        super().__init__()
        self.seed = seed
        rng = np.random.default_rng(seed)
        n = len(DRIVERS_2026)
        order = rng.permutation(n)
        self._drivers = pd.DataFrame([
            {"driver_number": d[0], "name_acronym": d[1], "team_name": d[2],
             "team_colour": d[3]} for d in DRIVERS_2026
        ])
        self._positions = pd.DataFrame([
            {"driver_number": DRIVERS_2026[i][0], "position": int(rank + 1),
             "name_acronym": DRIVERS_2026[i][1]}
            for rank, i in enumerate(order)
        ])
        self._laps = pd.DataFrame([
            {"driver_number": DRIVERS_2026[i][0], "lap_number": 18,
             "lap_duration": 96.0 + rng.uniform(0, 2.5), "sector_1_time": rng.uniform(26, 27.5),
             "sector_2_time": rng.uniform(27, 28.5), "sector_3_time": rng.uniform(40, 42)}
            for i in order
        ])
        self._weather = pd.DataFrame([
            {"air_temperature": 21.0, "track_temperature": 34.0,
             "humidity": 55, "rainfall": 0.0, "wind_speed": 8.0}
        ])
        self._race_control = pd.DataFrame([
            {"message": "Track conditions: dry", "category": "Flag",
             "flag": "GREEN", "source": "MOCK", "date": datetime.now(timezone.utc).isoformat()}
        ])
        self._stints = pd.DataFrame([
            {"driver_number": DRIVERS_2026[i][0], "compound": rng.choice(
                ["SOFT", "HARD"], p=[0.7, 0.3]), "lap_start": 1,
             "lap_end": None, "stint_length": 18}
            for i in order
        ])
        self._intervals = pd.DataFrame([
            {"driver_number": DRIVERS_2026[i][0], "gap_to_leader": 0.0 if i == order[0] else rng.uniform(0.5, 45.0),
             "interval": rng.uniform(0.1, 8.0)}
            for i in order
        ])

    def refresh(self) -> LiveSnapshot:
        return LiveSnapshot(
            source=self.name,
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            session={"circuit_short_name": "Melbourne", "session_name": "Race",
                      "country_name": "Australia", "year": 2026,
                      "date_start": None, "date_end": None},
            is_live=True,
            drivers=self._drivers,
            leaderboard=self._leaderboard(),
            latest_laps=self._laps,
            weather=self._weather,
            race_control=self._race_control,
            stints=self._stints,
            intervals=self._intervals,
            warnings=["mock provider - synthetic data, not real timing"],
        )

    def _leaderboard(self) -> pd.DataFrame:
        merged = self._positions.merge(
            self._drivers[["driver_number", "team_name", "team_colour"]],
            on="driver_number", how="left"
        )
        inter = self._intervals.merge(
            self._positions[["driver_number", "position"]], on="driver_number", how="left"
        )
        cols = ["driver_number", "position", "gap_to_leader", "interval", "name_acronym",
                "team_name", "team_colour"]
        return merged.merge(
            inter[["driver_number", "gap_to_leader", "interval"]],
            on="driver_number", how="left")[cols].sort_values("position")