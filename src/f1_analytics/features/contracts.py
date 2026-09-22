"""Feature contract audit for the 31-column training table."""

from __future__ import annotations

import pandas as pd

from ..data import load_training_dataset
from ..preprocessing import TARGETS, TRAINING_COLUMNS

# Column -> availability contract and null class.
# contract: pre_quali | post_quali | post_sprint | live | post_race
# null_class: cold_start | structural | not_applicable | true_zero | none
FEATURE_CONTRACTS: dict[str, dict[str, str]] = {
    "grid_position": {"contract": "post_quali", "null_class": "none",
                      "source": "qualifying/results", "description": "Starting grid position"},
    "grid_position_sq": {"contract": "post_quali", "null_class": "none",
                         "source": "derived", "description": "Grid squared (non-linear effect)"},
    "rolling_avg_finish_3": {"contract": "pre_quali", "null_class": "cold_start",
                             "source": "results", "description": "Average finish over prior 3 races"},
    "rolling_avg_finish_5": {"contract": "pre_quali", "null_class": "cold_start",
                             "source": "results", "description": "Average finish over prior 5 races"},
    "season_points_pct": {"contract": "pre_quali", "null_class": "none",
                          "source": "standings", "description": "Driver season points as share of leader"},
    "track_avg_finish": {"contract": "pre_quali", "null_class": "not_applicable",
                         "source": "results", "description": "Avg finish at this circuit (first visit = NA)"},
    "track_best_finish": {"contract": "pre_quali", "null_class": "not_applicable",
                          "source": "results", "description": "Best finish at this circuit"},
    "track_starts": {"contract": "pre_quali", "null_class": "none",
                     "source": "results", "description": "Number of prior starts at this circuit"},
    "dnf_rate_rolling_10": {"contract": "pre_quali", "null_class": "cold_start",
                            "source": "results/status", "description": "DNF rate across prior 10 races"},
    "quali_delta_teammate": {"contract": "post_quali", "null_class": "none",
                             "source": "qualifying", "description": "Quali time delta vs teammate"},
    "practice_pace_pct": {"contract": "pre_quali", "null_class": "structural",
                          "source": "fastf1_laps(2018+)",
                          "description": "Practice pace as % of field (unavailable pre-2018)"},
    "tyre_deg_rate": {"contract": "pre_quali", "null_class": "structural",
                      "source": "fastf1_laps", "description": "Tyre degradation rate estimate"},
    "constructor_avg_finish_5": {"contract": "pre_quali", "null_class": "cold_start",
                                 "source": "constructor_results",
                                 "description": "Constructor avg finish over prior 5 races"},
    "constructor_dnf_rate_10": {"contract": "pre_quali", "null_class": "cold_start",
                                "source": "results/status",
                                "description": "Constructor DNF rate over prior 10 races"},
    "constructor_season_points_pct": {"contract": "pre_quali", "null_class": "none",
                                      "source": "constructor_standings",
                                      "description": "Constructor season points as share of leader"},
    "constructor_avg_speed_trap": {"contract": "pre_quali", "null_class": "structural",
                                   "source": "fastf1_laps",
                                   "description": "Constructor average speed trap (coverage-limited)"},
    "pit_stop_avg_ms": {"contract": "post_race", "null_class": "not_applicable",
                        "source": "pit_stops",
                        "description": "Driver avg pit-stop duration. LEAKAGE under pre-race contracts - see audit"},
    "air_temp": {"contract": "pre_quali", "null_class": "structural",
                 "source": "session_weather", "description": "Air temperature (use forecast pre-race)"},
    "track_temp": {"contract": "pre_quali", "null_class": "structural",
                   "source": "session_weather", "description": "Track temperature (use forecast pre-race)"},
    "rainfall": {"contract": "pre_quali", "null_class": "true_zero",
                 "source": "session_weather", "description": "Rainfall 0/1; 0 is a real value"},
    "safety_car_prob": {"contract": "pre_quali", "null_class": "structural",
                        "source": "tracks.yaml", "description": "Safety-car probability prior"},
}


def feature_audit() -> pd.DataFrame:
    """Human-readable audit of every feature contract."""
    rows = []
    for col, meta in FEATURE_CONTRACTS.items():
        rows.append({
            "feature": col,
            "contract": meta["contract"],
            "null_class": meta["null_class"],
            "source": meta["source"],
            "description": meta["description"],
        })
    return pd.DataFrame(rows)


def leaking_features(contract: str) -> list[str]:
    """features unavailable at the given prediction contract (post_quali, pre_quali)."""
    order = {"pre_quali": 0, "post_quali": 1, "post_sprint": 2, "live": 3, "post_race": 4}
    bad = []
    for col, meta in FEATURE_CONTRACTS.items():
        # A feature whose own availability is LATER than the requested contract leaks.
        if order[meta["contract"]] > order[contract]:
            bad.append(col)
    return bad


def is_leakage_free(df: pd.DataFrame, contract: str, inputs: list[str]) -> tuple[bool, list[str]]:
    leaks = [c for c in inputs if c in leaking_features(contract)]
    return (not leaks), leaks


def training_table() -> pd.DataFrame:
    """The audited (as-is) training table (raw 31 columns)."""
    return load_training_dataset()


def split_years(df: pd.DataFrame, train_max: int = 2022,
                val_years: tuple[int, int] = (2023, 2024),
                test_years: tuple[int, int] = (2025,)) -> tuple[pd.DataFrame, ...]:
    """Chronological train / validation / test / holdout split."""
    train = df[df["year"] <= train_max]
    val = df[df["year"].between(*val_years)]
    test = df[df["year"].isin(test_years)] if test_years else pd.DataFrame(columns=df.columns)
    holdout = df[df["year"] > max((tuple(val_years) + tuple(test_years)))]
    return train, val, test, holdout