"""Race simulation (Phase 6): lap-by-lap Monte Carlo from tracks.yaml +
driver_profiles + starting grid. Outputs are labeled hypothetical."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..data import load_driver_profiles, load_tracks


@dataclass
class SimResult:
    seed: int
    n_runs: int
    place: pd.DataFrame  # driver x {wins, podiums, dnfs, avg_finish}
    lap_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_sim_summary(self) -> dict:
        return {
            "seed": self.seed,
            "n_runs": self.n_runs,
            "laps": self.lap_count,
            "warnings": self.warnings,
            "winner_freq": self.place.sort_values("wins", ascending=False)
            [["driver", "wins", "podiums", "dnfs"]].to_dict(orient="records"),
        }


def _mapped_tracks() -> dict[str, dict]:
    return load_tracks()


def simulate(seed: int = 42, n_runs: int = 100, track_key: str = "melbourne",
             grid: list[str] | None = None) -> SimResult:
    tracks = _mapped_tracks()
    warnings: list[str] = []
    if track_key not in tracks:
        warnings.append(f"track {track_key!r} not in tracks.yaml - using melbourne defaults")
        track_key = "melbourne"
    params = tracks[track_key]

    profiles = load_driver_profiles()
    if profiles.empty:
        warnings.append("driver_profiles.parquet empty - using uniform pace")

    drivers = grid or list(profiles["driverRef"])[:20] if not profiles.empty else \
        ["VER", "NOR", "PIA", "SAI", "LEC", "HAM", "RUS", "ALO", "STR", "OCO",
         "GAS", "ZHO", "BOT", "TSU", "LAW"]
    if not drivers:
        warnings.append("no drivers; simulation aborted")
        return SimResult(seed=seed, n_runs=n_runs, place=pd.DataFrame(), warnings=warnings)

    rng = np.random.default_rng(seed)
    laps = int(params.get("laps", 56))
    sc_prob = float(params.get("safety_car_probability", 0.2))
    rain_prob = float(params.get("rain_probability", 0.3))
    tyre_mult = float(params.get("tire_degradation_multiplier", 1.0))
    overtaking = float(params.get("overtaking_difficulty", 0.5))
    pit_loss = float(params.get("pit_time_loss_seconds", 18.0))
    dnf_base = 0.167  # calibration target

    pace = {}
    for d in drivers:
        row = profiles[profiles["driverRef"] == d] if not profiles.empty else pd.DataFrame()
        base = (float(row["race_pace"].iloc[0]) if not row.empty else 0.5) * 1.5 + 94.0
        pace[d] = max(80.0, base)
    pace = {d: p for d, p in sorted(pace.items(), key=lambda kv: kv[1])}

    agg = {d: {"wins": 0, "podiums": 0, "dnfs": 0, "finishes": []} for d in drivers}

    for run in range(n_runs):
        order = list(drivers)
        # grid shuffle mildly
        rng.shuffle(order)
        running = {d: {"lap": 0, "time": 0.0, "alive": True, "gaps": rng.normal(0, 0.2, 1)[0]} for d in order}
        leader_prime = 0.0
        for lap in range(1, laps + 1):
            # per-lap time = base + tyre deg drift + noise; SC occasionally neutralizes
            sc_active = rng.random() < sc_prob and lap > 5
            for d, st in running.items():
                if not st["alive"]:
                    continue
                if rng.random() < (dnf_base / laps) * (1.2 if sc_active else 1.0):
                    st["alive"] = False
                    agg[d]["dnfs"] += 1
                    continue
                ty = st["lap"] * 0.0015 * tyre_mult
                st["time"] += pace[d] * (1 + ty) + (10.0 if sc_active else 0.0) + \
                    (rng.normal(0, 0.4) * (1 + overtaking))
                st["lap"] += 1
            # drop in/out after pit-ish: 1 stop ~ pit loss
            if lap % (laps // 3) == 0:
                for d, st in running.items():
                    if st["alive"] and rng.random() < 0.5:
                        st["time"] += pit_loss
            if sc_active:
                continue
            # rough overtake: swap adjacent lower-time ahead
            ordered = sorted([d for d, st in running.items() if st["alive"]],
                             key=lambda d: running[d]["time"])
            for i in range(len(ordered) - 1):
                if running[ordered[i]]["time"] - running[ordered[i + 1]]["time"] > 0.05 and \
                        rng.random() > overtaking:
                    ordered[i], ordered[i + 1] = ordered[i + 1], ordered[i]

        finish = [d for d in ordered if running[d]["alive"]]
        for rank, d in enumerate(finish, start=1):
            agg[d]["finishes"].append(rank)
            if rank == 1:
                agg[d]["wins"] += 1
            if rank <= 3:
                agg[d]["podiums"] += 1

    rows = []
    for d in drivers:
        finishes = agg[d]["finishes"]
        rows.append({
            "driver": d,
            "wins": agg[d]["wins"],
            "podiums": agg[d]["podiums"],
            "dnfs": agg[d]["dnfs"],
            "win_pct": 100.0 * agg[d]["wins"] / max(1, n_runs),
            "podium_pct": 100.0 * agg[d]["podiums"] / max(1, n_runs),
            "avg_finish": float(np.mean(finishes)) if finishes else None,
            "races_finished": len(finishes),
        })
    place = pd.DataFrame(rows).sort_values("wins", ascending=False).reset_index(drop=True)
    return SimResult(seed=seed, n_runs=n_runs, place=place, lap_count=laps, warnings=warnings)