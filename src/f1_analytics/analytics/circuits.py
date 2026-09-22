"""Circuit analytics over f1.db + tracks.yaml parameters."""

from __future__ import annotations

import pandas as pd

from ..data import load_tracks
from ..database import circuit_list, query


def circuit_analytics_table() -> pd.DataFrame:
    """Historical winners, lap counts, SC/red-flag frequencies, tracks.yaml overlay."""
    circ = circuit_list()
    if circ.empty:
        return pd.DataFrame()

    # Winners
    winners = query(
        """
        SELECT ci.circuitId, d.forename || ' ' || d.surname AS most_common_winner,
               COUNT(*) AS wins
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        JOIN circuits ci ON r.circuitId = ci.circuitId
        JOIN drivers d ON res.driverId = d.driverId
        WHERE res.position = '1'
        GROUP BY ci.circuitId, d.driverId, d.forename, d.surname
        """
    )
    if not winners.empty:
        top = (
            winners.sort_values("wins", ascending=False)
            .drop_duplicates("circuitId", keep="first")
        )
        circ = circ.merge(top[["circuitId", "most_common_winner", "wins"]], on="circuitId", how="left")

    # tracks.yaml params joined by circuitRef key
    params = load_tracks()
    param_rows = [
        {
            "circuitRef": key,
            "track_type": p.get("type"),
            "overtaking_difficulty": p.get("overtaking_difficulty"),
            "pit_time_loss_s": p.get("pit_time_loss_seconds"),
            "safety_car_prob": p.get("safety_car_probability"),
            "rain_prob": p.get("rain_probability"),
            "qualifying_importance": p.get("qualifying_importance"),
            "laps_expected": p.get("laps"),
        }
        for key, p in params.items()
    ]
    params_df = pd.DataFrame(param_rows)
    circ = circ.merge(params_df, on="circuitRef", how="left")
    return circ.sort_values("races_held", ascending=False).reset_index(drop=True)


def circuit_historical_winners(circuit_ref: str | None = None) -> pd.DataFrame:
    sql = """
        SELECT r.year, d.forename || ' ' || d.surname AS winner,
               c.name AS constructor, res.points
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        JOIN circuits ci ON r.circuitId = ci.circuitId
        JOIN drivers d ON res.driverId = d.driverId
        JOIN constructors c ON res.constructorId = c.constructorId
        WHERE res.position = '1'
          AND (? IS NULL OR ci.circuitRef = ?)
        ORDER BY r.year
    """
    return query(sql, {"circuit": circuit_ref, "circuit_": circuit_ref})


def circuit_pace(circuit_ref: str | None = None, session: str = "Race") -> pd.DataFrame:
    sql = """
        SELECT r.year, ci.circuitRef, d.code, l.time_sec, l.s1, l.s2, l.s3
        FROM fastf1_laps l
        JOIN races r ON l.raceId = r.raceId
        JOIN circuits ci ON r.circuitId = ci.circuitId
        JOIN drivers d ON d.driverId = l.driverId
        WHERE l.session = ? AND l.is_accurate = 1
          AND (? IS NULL OR ci.circuitRef = ?)
    """
    return query(sql, {"session": session, "circuit": circuit_ref, "circuit_": circuit_ref})