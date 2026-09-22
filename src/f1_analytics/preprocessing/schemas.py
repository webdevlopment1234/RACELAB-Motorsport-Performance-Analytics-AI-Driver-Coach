"""Schema contracts for every data source (measured against the dataset)."""

from __future__ import annotations

# Column -> expected dtypes (nullable columns omitted from strict checks).
# The training table null-profile lives in FEATURE_NULL_PROFILE for drift
# detection of missing-value patterns.

CSV_SCHEMAS: dict[str, dict[str, str]] = {
    "circuits": {"circuitId": "int", "circuitRef": "str", "name": "str"},
    "constructor_results": {"constructorResultsId": "int", "raceId": "int", "constructorId": "int"},
    "constructor_standings": {"constructorStandingsId": "int", "raceId": "int", "constructorId": "int"},
    "constructors": {"constructorId": "int", "constructorRef": "str", "name": "str"},
    "driver_standings": {"driverStandingsId": "int", "raceId": "int", "driverId": "int"},
    "drivers": {"driverId": "int", "driverRef": "str", "surname": "str"},
    "lap_times": {"raceId": "int", "driverId": "int", "lap": "int", "milliseconds": "int"},
    "pit_stops": {"raceId": "int", "driverId": "int", "stop": "int", "lap": "int"},
    "qualifying": {"qualifyId": "int", "raceId": "int", "driverId": "int"},
    "races": {"raceId": "int", "year": "int", "round": "int", "circuitId": "int"},
    "results": {"resultId": "int", "raceId": "int", "driverId": "int", "constructorId": "int"},
    "seasons": {"year": "int"},
    "sprint_results": {"resultId": "int", "raceId": "int", "driverId": "int"},
    "status": {"statusId": "int"},
}

CSV_ROW_COUNTS = {
    "circuits": 77,
    "constructor_results": 12625,
    "constructor_standings": 13391,
    "constructors": 212,
    "driver_standings": 34863,
    "drivers": 861,
    "lap_times": 589081,
    "pit_stops": 11371,
    "qualifying": 10494,
    "races": 1125,
    "results": 26759,
    "seasons": 75,
    "sprint_results": 360,
    "status": 139,
}

DB_ROW_COUNTS = {
    "circuits": 78,
    "constructors": 214,
    "drivers": 865,
    "races": 1171,
    "seasons": 77,
    "results": 27235,
    "qualifying": 11058,
    "lap_times": 619804,
    "pit_stops": 12294,
    "driver_standings": 35449,
    "constructor_standings": 13675,
    "constructor_results": 12909,
    "sprint_results": 524,
    "status": 140,
    "fastf1_laps": 481075,
    "session_weather": 86433,
    "race_control": 37155,
    "safety_cars": 364,
    "red_flags": 98,
    "circuit_corners": 14361,
}

TRAINING_COLUMNS = [
    "raceId", "driverId", "constructorId", "year", "round", "circuitId",
    "grid_position", "rolling_avg_finish_3", "rolling_avg_finish_5",
    "season_points_pct", "track_avg_finish", "track_best_finish",
    "track_starts", "dnf_rate_rolling_10", "quali_delta_teammate",
    "practice_pace_pct", "tyre_deg_rate", "finish", "is_dnf",
    "constructor_avg_finish_5", "constructor_dnf_rate_10",
    "constructor_season_points_pct", "constructor_avg_speed_trap",
    "pit_stop_avg_ms", "air_temp", "track_temp", "rainfall",
    "safety_car_prob", "grid_position_sq", "is_winner", "is_podium",
]

TARGETS = ["finish", "is_dnf", "is_winner", "is_podium"]

FEATURE_COLUMNS = [c for c in TRAINING_COLUMNS if c not in TARGETS and c not in
                   ("raceId", "driverId", "constructorId")]

# Null-profile expected for driver/race feature columns (fraction).
TRAINING_NULL_PROFILE = {
    "practice_pace_pct": 0.367,
    "tyre_deg_rate": 0.359,
    "constructor_avg_speed_trap": 0.326,
    "air_temp": 0.325,
    "track_temp": 0.325,
    "rainfall": 0.325,
    "track_avg_finish": 0.204,
    "track_best_finish": 0.204,
    "safety_car_prob": 0.051,
    "rolling_avg_finish_3": 0.008,
    "rolling_avg_finish_5": 0.008,
    "dnf_rate_rolling_10": 0.008,
    "pit_stop_avg_ms": 0.004,
    "constructor_avg_finish_5": 0.004,
    "constructor_dnf_rate_10": 0.004,
}

DRIVER_PROFILES_COLUMNS = [
    "driverId", "driverRef", "code", "name", "nationality",
    "first_year", "last_year", "total_races", "total_wins",
    "total_podiums", "quali_dominance", "race_pace", "consistency",
    "wet_mastery", "overtaking", "teammate_dominance", "peak_rating",
    "overall_rating",
]

TRACKS_REQUIRED_FIELDS = [
    "name", "type", "overtaking_difficulty", "pit_time_loss_seconds",
    "safety_car_probability", "tire_degradation_multiplier",
    "rain_probability", "qualifying_importance", "laps",
]

TRACKS_KEYS = [
    "bahrain", "baku", "barcelona", "cota", "hungaroring", "imola",
    "interlagos", "jeddah", "las_vegas", "losail", "melbourne", "mexico",
    "monaco", "montreal", "monza", "red_bull_ring", "shanghai",
    "silverstone", "singapore", "spa", "suzuka", "yas_marina", "zandvoort",
]