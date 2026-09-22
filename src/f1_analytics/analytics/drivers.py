"""Driver analytics over f1.db + driver_profiles.parquet."""

from __future__ import annotations

import pandas as pd

from ..data import load_driver_profiles
from ..database import driver_list, driver_sessions


def driver_summary_table() -> pd.DataFrame:
    """Wins, podiums, average finish, starts per driver (names included)."""
    sess = driver_sessions()  # all sessions
    if sess.empty:
        return pd.DataFrame()
    agg = (
        sess.groupby("driverId")
        .agg(
            starts=("positionOrder", "count"),
            wins=("position", lambda s: (s == "1").sum()),
            podiums=("position", lambda s: s.isin(["1", "2", "3"]).sum()),
            dnf=(("position", lambda s: s.isna().sum())),
        )
        .reset_index()
    )
    # average finish among classified finishers
    fin = sess[sess["position"].notna()].copy()
    fin["positionOrder"] = pd.to_numeric(fin["positionOrder"], errors="coerce")
    avg = fin.groupby("driverId")["positionOrder"].mean().rename("avg_finish")
    agg = agg.merge(avg, on="driverId", how="left")
    agg["dnf_rate"] = (agg["dnf"] / agg["starts"]).fillna(0.0)
    # attach driver names from driver_list (drop its start/wins to avoid collision)
    names = driver_list()[["driverId", "code", "forename", "surname", "driverRef"]]
    agg = agg.merge(names, on="driverId", how="left")
    agg["driver"] = agg["forename"].fillna("") + " " + agg["surname"].fillna("")
    agg = agg.sort_values("wins", ascending=False).reset_index(drop=True)
    # Join ratings from driver_profiles where available
    try:
        profiles = load_driver_profiles()
        profile_cols = {
            "driverId": "driverId", "overall_rating": "overall_rating",
            "race_pace": "race_pace", "consistency": "consistency",
            "quali_dominance": "quali_dominance", "wet_mastery": "wet_mastery",
            "overtaking": "overtaking",
        }
        agg = agg.merge(
            profiles[list(profile_cols)].rename(columns=profile_cols),
            on="driverId", how="left",
        )
    except Exception:  # noqa: BLE001 - profiles are enrichment
        pass
    return agg


def driver_session_history(driver_id: int) -> pd.DataFrame:
    return driver_sessions(driver_id=driver_id)


def driver_head_to_head(driver_a: int, driver_b: int) -> pd.DataFrame:
    """Finishing positions of two drivers across shared races."""
    a = driver_sessions(driver_id=driver_a)[["year", "round", "race_name", "positionOrder"]]
    b = driver_sessions(driver_id=driver_b)[["year", "round", "race_name", "positionOrder"]]
    a = a.rename(columns={"positionOrder": "driver_a"})
    b = b.rename(columns={"positionOrder": "driver_b"})
    return a.merge(b, on=["year", "round", "race_name"], how="inner").sort_values(["year", "round"])