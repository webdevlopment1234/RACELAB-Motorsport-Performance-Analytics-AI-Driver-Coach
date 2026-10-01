"""Evidence-based, numerical AI Driver Coach (Phase 9).

Never coaches on incomplete/incomparable/low-confidence data. Outputs
are structured: evidence -> findings -> recommendations, each with
conditions and confidence. Live coach (Phase 10) uses the same
evidence->finding pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..database import lap_pace, lap_pace_race


@dataclass
class Finding:
    area: str
    text: str
    confidence: float
    conditions: str = ""


@dataclass
class CoachReport:
    driver: str
    n_laps: int
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def markdown(self) -> str:
        lines = [f"# Coach Report - {self.driver}", f"Laps analyzed: {self.n_laps}"]
        if self.warnings:
            lines.append("\n**Caveats:** " + "; ".join(self.warnings))
        if not self.findings:
            lines.append("\nNo findings - insufficient comparable data.")
            return "\n".join(lines)
        lines.append("\n## Findings")
        for f in self.findings:
            lines.append(f"- **{f.area}** (confidence {f.confidence:.0%}): {f.text}"
                         + (f" [{f.conditions}]" if f.conditions else ""))
        return "\n".join(lines)


def _sector_norm(t: float | None) -> float | None:
    return float(t) if t is not None and pd.notna(t) else None


def coach_laps(driver_id: int, session: str = "Race",
               year_min: int = 2018, year_max: int = 2026) -> CoachReport:
    laps = lap_pace(session, year_min, year_max)
    if laps.empty:
        return CoachReport(driver=str(driver_id), n_laps=0,
                           warnings=["no lap data for this driver/session"])
    mine = laps[laps["driverId"] == driver_id]
    if mine.empty:
        return CoachReport(driver=str(driver_id), n_laps=0,
                           warnings=["driver not found in lap dataset"])
    clean = mine[mine["track_status"] == "1"][
        [c for c in ("time_sec", "s1", "s2", "s3", "constructor") if c in mine.columns]
    ].dropna()
    if clean.empty or len(clean) < 3:
        return CoachReport(driver=str(driver_id),
                           n_laps=int(mine.shape[0]),
                           warnings=["not enough comparable (green-track) laps"])
    report = CoachReport(driver=str(driver_id), n_laps=int(clean.shape[0]))
    best_lap = clean["time_sec"].min()
    if len(clean) >= 8:
        cols = [c for c in ("s1", "s2", "s3") if c in clean.columns]
        for sector in cols:
            if sector not in clean or clean[sector].nunique() < 2:
                continue
            worst = clean.sort_values(sector, ascending=False).iloc[0]
            best = clean.sort_values(sector, ascending=True).iloc[0]
            delta = float(worst[sector] - best[sector])
            if delta < 0.02:
                continue
            report.findings.append(Finding(
                area=f"Sector {sector[-1]} consistency",
                text=(f"Most inconsistent {sector[-1]}; worst lap {worst[sector]:.3f}s "
                      f"vs best {best[sector]:.3f}s (delta {delta:.3f}s)"),
                confidence=0.8,
                conditions=f"n={len(clean)} green-track laps",
            ))
    # average vs field
    field_best = laps[laps["track_status"] == "1"]["time_sec"].dropna().min()
    pace_gap = float(best_lap - field_best)
    report.findings.append(Finding(
        area="Overall pace",
        text=f"Best lap {best_lap:.2f}s vs field best {field_best:.2f}s (gap {pace_gap:+.3f}s)",
        confidence=0.9 if len(clean) >= 10 else 0.6,
        conditions=f"best of {len(clean)} clean laps, {'dry-flag' if 'rainfall' not in clean else 'mixed'}",
    ))
    return report


def live_coach_from_snapshot(snapshot) -> CoachReport:
    """Phase 10: coach findings from a live snapshot (leaderboard order)."""
    lb = snapshot.leaderboard
    if lb.empty:
        return CoachReport(driver="live", n_laps=0, warnings=["no live leaderboard"])
    rows = []
    for _, r in lb.iterrows():
        rows.append(f"P{int(r['position'])} {r.get('name_acronym', '')}")
    return CoachReport(
        driver="live",
        n_laps=0,
        findings=[Finding("Live standing", " | ".join(rows), confidence=0.95,
                          conditions=f"source={snapshot.source} fresh {snapshot.fetched_at}")],
        warnings=["live coach only ranks current order; lap-level needs telemetry"],
    )


def coach_race(race_id: int, driver_id: int) -> CoachReport:
    """Post-session coach for a single race (Phase 9, race-scoped).

    Compares the driver's clean green-track laps against the race field:
    overall pace gap, sector consistency, and the tyre context of the best
    lap. Corner-level loss ("0.2s at Turn 4") needs continuous car data +
    circuit_corners, which is reported as an explicit caveat when absent.
    """
    laps = lap_pace_race(race_id)
    if laps.empty:
        return CoachReport(driver=str(driver_id), n_laps=0,
                           warnings=["no fastf1_laps for this race (f1.db required)"])
    green = laps[laps["track_status"].astype(str) == "1"].copy()
    if green.empty:
        return CoachReport(driver=str(driver_id), n_laps=int(laps.shape[0]),
                           warnings=["no clean green-track laps in this race"])
    mine = green[green["driverId"] == driver_id]
    if mine.empty:
        name = laps[laps["driverId"] == driver_id]["driver"].iloc[0] if (
            laps["driverId"] == driver_id).any() else str(driver_id)
        return CoachReport(driver=name, n_laps=int(laps.shape[0]),
                           warnings=["driver has no clean laps in this race"])
    name = mine["driver"].iloc[0]
    report = CoachReport(driver=name, n_laps=int(mine.shape[0]))
    best_lap = mine["time_sec"].min()
    field_best = green["time_sec"].min()
    pace_gap = float(best_lap - field_best)
    report.findings.append(Finding(
        area="Race pace",
        text=f"Best lap {best_lap:.3f}s vs race field best {field_best:.3f}s "
             f"(gap {pace_gap:+.3f}s)",
        confidence=0.9 if len(mine) >= 8 else 0.6,
        conditions=f"{len(mine)} clean laps, green only",
    ))
    if len(mine) >= 6:
        for sector in ("s1", "s2", "s3"):
            if sector not in mine.columns or mine[sector].nunique() < 2:
                continue
            worst = mine.sort_values(sector, ascending=False).iloc[0]
            best = mine.sort_values(sector, ascending=True).iloc[0]
            delta = float(worst[sector] - best[sector])
            if delta < 0.02:
                continue
            report.findings.append(Finding(
                area=f"Sector {sector[-1]} consistency",
                text=f"Most inconsistent in sector {sector[-1]}: lap {int(worst['lap'])} "
                     f"{worst[sector]:.3f}s vs best {best[sector]:.3f}s "
                     f"(delta {delta:+.3f}s)",
                confidence=0.75,
                conditions=f"n={len(mine)} clean laps",
            ))
    best_row = mine.loc[mine["time_sec"].idxmin()]
    if "compound" in best_row and "tyre_life" in best_row:
        report.findings.append(Finding(
            area="Best-lap tyre context",
            text=(f"Fastest lap set on {best_row['compound']} at {int(best_row['tyre_life'])} "
                  f"laps old (stint {int(best_row['stint'])})"),
            confidence=0.85,
            conditions="from fastf1_laps",
        ))
    report.warnings.append(
        "Corner-level loss ('0.2s at Turn 4') requires continuous car data "
        "with circuit_corners - not available for this race yet.")
    return report