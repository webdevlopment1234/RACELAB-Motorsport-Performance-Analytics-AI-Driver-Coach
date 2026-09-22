"""Constructor analytics over f1.db."""

from __future__ import annotations

import pandas as pd

from ..database import constructor_list, query


def constructor_summary_table() -> pd.DataFrame:
    """Championship points, starts, DNF rate, avg finish per constructor."""
    con = constructor_list()
    if con.empty:
        return pd.DataFrame()
    res = query(
        """
        SELECT res.constructorId, res.points, res.positionOrder,
               CASE WHEN st.statusId = 1 THEN 0 ELSE 1 END AS is_dnf
        FROM results res JOIN status st ON res.statusId = st.statusId
        """
    )
    agg = (
        res.groupby("constructorId")
        .agg(
            starts=("points", "count"),
            total_points=("points", "sum"),
            dnf=(("is_dnf", lambda s: int(s.sum()))),
            avg_finish=("positionOrder", "mean"),
        )
        .reset_index()
    )
    agg["dnf_rate"] = (agg["dnf"] / agg["starts"]).fillna(0.0)
    out = con.drop(columns=["starts"]).merge(agg, on="constructorId", how="left")
    out = out.fillna({"starts": 0, "total_points": 0, "dnf_rate": 0.0})
    return out.sort_values("total_points", ascending=False).reset_index(drop=True)


def constructor_pit_stop_stats() -> pd.DataFrame:
    """Average pit-stop duration per constructor from CSV-like pit_stops."""
    # pit_stops lacks constructorId, so resolve via results
    return query(
        """
        SELECT c.name AS constructor, COUNT(*) AS stops,
               AVG(ps.milliseconds) / 1000.0 AS avg_duration_s
        FROM pit_stops ps
        JOIN (SELECT resultId, raceId, driverId, constructorId FROM results) res
          ON res.raceId = ps.raceId AND res.driverId = ps.driverId
        JOIN constructors c ON c.constructorId = res.constructorId
        WHERE ps.milliseconds IS NOT NULL
        GROUP BY c.name
        ORDER BY avg_duration_s
        """
    ).drop_duplicates(subset="constructor")


def constructor_season_points(year: int) -> pd.DataFrame:
    return query(
        """
        SELECT c.name AS constructor, cs.wins, cs.position, cs.points
        FROM constructor_standings cs
        JOIN races r ON cs.raceId = r.raceId
        JOIN constructors c ON cs.constructorId = c.constructorId
        WHERE r.year = ? AND r.round = (SELECT MAX(round) FROM races WHERE year = ?)
        ORDER BY cs.position
        """,
        {"year": year, "year_": year},
    )