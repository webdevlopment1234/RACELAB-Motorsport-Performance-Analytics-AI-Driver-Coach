"""Race Intelligence page (RACELAB) - the flagship screen.

Implements the dashboard mockup layout:

    TIMING  |  TRACK MAP            |  TELEMETRY (gauges)
    SPEED / THROTTLE / BRAKE / GEAR / DELTA   (chart)
    TYRE STRATEGY                  |  AI DRIVER COACH

Three modes: LIVE RACE (from the live provider snapshot), HISTORICAL
(f1.db race), and AI COACH. Every panel degrades gracefully when its data
source is unavailable and never fabricates values: missing telemetry feeds
fall back to real per-lap pace data from fastf1_laps, and synthetic data
is always labeled (mock provider).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from skin import gauge, hero, intel_chip, intel_label, intel_row, led, pod  # noqa: E402

from f1_analytics import config  # noqa: E402
from f1_analytics.assistant import LLMClient, ask  # noqa: E402
from f1_analytics.coach import coach_race, live_coach_from_snapshot  # noqa: E402
from f1_analytics.data import DataNotFoundError, db_available  # noqa: E402
from f1_analytics.database import query, race_results  # noqa: E402
from f1_analytics.live import create_provider  # noqa: E402
from f1_analytics.logging_utils import log_error  # noqa: E402

PAGE_NAME = "Race Intelligence"
_MODES = ("LIVE RACE", "HISTORICAL", "AI COACH")

_COMPOUND_COLOURS = {
    "SOFT": "#ff3b30",
    "MEDIUM": "#ffd700",
    "HARD": "#e8ebf0",
    "INTERMEDIATE": "#34c759",
    "WET": "#0a84ff",
    "C5": "#ff3b30", "C4": "#ffd700", "C3": "#e8ebf0",
    "C2": "#c0c7d1", "C1": "#8f95a0",
}

_RACE_SQL = (
    "SELECT r.raceId, r.year, r.round, r.name AS event, "
    "c.name AS circuit, c.circuitRef, c.location, c.country "
    "FROM races r JOIN circuits c ON r.circuitId = c.circuitId "
    "ORDER BY r.year, r.round"
)

_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, Consolas, monospace", color="#e8ebf0"),
    margin=dict(l=8, r=8, t=24, b=8),
    height=300,
    showlegend=True,
    legend=dict(orientation="h", y=-0.18, font=dict(size=10)),
)


def _layout(**overrides) -> dict:
    cfg = dict(_LAYOUT)
    cfg.update(overrides)
    return cfg


@st.cache_data(show_spinner=False)
def _races_with_circuit() -> pd.DataFrame:
    return query(_RACE_SQL)


@st.cache_resource(show_spinner=False)
def _provider_cache(name: str):
    return create_provider(name)


def _live_snapshot():
    """Return (snapshot, error). Never raises on offline providers."""
    try:
        name = st.session_state.get("provider", config.LIVE_PROVIDER)
        snap = _provider_cache(name).snapshot()
        if snap is None:
            return None, f"{name} returned no snapshot (offline)"
        return snap, ""
    except Exception as exc:  # noqa: BLE001 - live panels must never crash
        log_error("race-intel live error: %s", exc)
        return None, f"{name} unavailable: {exc}"


# ---------------------------------------------------------------------------
# Track map
# ---------------------------------------------------------------------------

def _corners_for_circuit(hint: str) -> pd.DataFrame:
    """Real track geometry (x/y per corner) for the circuit matching hint."""
    if not db_available():
        return pd.DataFrame()
    try:
        races = _races_with_circuit()
    except DataNotFoundError:
        return pd.DataFrame()
    if races.empty:
        return pd.DataFrame()
    if hint:
        h = str(hint).strip().lower()
        mask = (
            races["circuit"].str.lower().str.contains(h, regex=False)
            | races["location"].str.lower().str.contains(h, regex=False)
            | races["country"].str.lower().str.contains(h, regex=False)
        )
        candidates = races[mask]
    else:
        candidates = races
    for _, row in candidates.iterrows():  # newest race first
        try:
            corners = query(
                "SELECT corner_num, x, y, angle, distance FROM circuit_corners "
                "WHERE raceId = ? ORDER BY corner_num",
                {"1": int(row["raceId"])},
            )
        except DataNotFoundError:
            return pd.DataFrame()
        if not corners.empty:
            corners.attrs["circuit"] = str(row["circuit"])
            return corners
    return pd.DataFrame()


def _corners_for_race(race_id: int | None) -> pd.DataFrame:
    if race_id is None or not db_available():
        return pd.DataFrame()
    try:
        return query(
            "SELECT corner_num, x, y, angle, distance FROM circuit_corners "
            "WHERE raceId = ? ORDER BY corner_num",
            {"1": int(race_id)},
        )
    except DataNotFoundError:
        return pd.DataFrame()


def _closed_outline(corners: pd.DataFrame) -> pd.DataFrame:
    if corners.empty:
        return corners
    return pd.concat([corners, corners.iloc[[0]]], ignore_index=True)


def _resample_outline(corners: pd.DataFrame, n: int) -> np.ndarray:
    """Evenly spaced points along the corner polyline (approx. car markers)."""
    closed = _closed_outline(corners)
    pts = closed[["x", "y"]].to_numpy(dtype=float)
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    total = seg.sum()
    if total <= 0:
        return pts[:1]
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    targets = np.linspace(0.0, total, n)
    return np.column_stack([np.interp(targets, cum, pts[:, 0]),
                            np.interp(targets, cum, pts[:, 1])])


def _track_figure(corners: pd.DataFrame, markers: pd.DataFrame | None = None) -> go.Figure:
    fig = go.Figure()
    if corners.empty:
        t = np.linspace(0.0, 2 * np.pi, 90)
        fig.add_trace(go.Scatter(
            x=300 * np.cos(t), y=180 * np.sin(t), mode="lines",
            line=dict(color="#4d545e", width=3), hoverinfo="skip",
            fill="toself", fillcolor="rgba(60,68,78,0.25)", name="track (generic)"))
    else:
        outline = _closed_outline(corners)
        fig.add_trace(go.Scatter(
            x=outline["x"], y=outline["y"], mode="lines",
            line=dict(color="#4d545e", width=3), hoverinfo="skip",
            fill="toself", fillcolor="rgba(60,68,78,0.25)", name="track"))
    if markers is not None and not markers.empty:
        fig.add_trace(go.Scatter(
            x=markers["x"], y=markers["y"], mode="markers+text",
            text=markers["name"], textposition="top center",
            textfont=dict(size=9, color="#e8ebf0"),
            marker=dict(size=15, color=markers["colour"], line=dict(color="#0b0d10", width=2)),
            hovertemplate="%{text}<extra></extra>",
            name="cars (approx)"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(**_layout(showlegend=False, height=330))
    return fig


def _markers_from_leaderboard(lb: pd.DataFrame, corners: pd.DataFrame, n: int = 10) -> pd.DataFrame | None:
    """Approximate marker positions derived from live order*(only meaningful for mock)."""
    if corners.empty or lb is None or lb.empty:
        return None
    pts = _resample_outline(corners, n)
    rows = []
    for i, (_, row) in enumerate(lb.head(n).iterrows()):
        rows.append({
            "x": pts[i][0], "y": pts[i][1],
            "name": row.get("name_acronym") or row.get("driver") or str(row.get("position", "?")),
            "colour": row.get("team_colour") or "#8f95a0",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Telemetry charts
# ---------------------------------------------------------------------------

def _live_telemetry(snap) -> pd.DataFrame:
    """Per-driver one-lap telemetry from the snapshot (mock/synthetic only)."""
    if snap.telemetry is None or snap.telemetry.empty:
        return pd.DataFrame()
    return snap.telemetry


def _gauges(snap) -> None:
    """SPEED / THROTTLE / BRAKE / GEAR chrome gauges."""
    tele = _live_telemetry(snap)
    speed = None
    if not tele.empty and "speed_kmh" in tele:
        speed = float(tele["speed_kmh"].iloc[-1])
    elif snap.latest_laps is not None and not snap.latest_laps.empty:
        for c in ("speed_trap", "st_speed", "speed_fl", "speed_i1", "speed_i2"):
            if c in snap.latest_laps.columns and snap.latest_laps[c].notna().any():
                speed = float(snap.latest_laps[c].dropna().iloc[0])
                break
    throttle = float(tele["throttle_pct"].iloc[-1]) if not tele.empty and "throttle_pct" in tele else None
    brake = float(tele["brake_pct"].iloc[-1]) if not tele.empty and "brake_pct" in tele else None
    gear = int(tele["gear"].iloc[-1]) if not tele.empty and "gear" in tele else None
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(gauge(f"{speed:.0f}" if speed is not None else "—",
                          "SPEED · km/h", (speed / 360.0) if speed else 0.0,
                          "114,179,255"),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(gauge(f"{throttle:.0f}" if throttle is not None else "—",
                          "THROTTLE · %", (throttle / 100.0) if throttle else 0.0,
                          "255,159,10"),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(gauge(f"{brake:.0f}" if brake is not None else "—",
                          "BRAKE · %", (brake / 100.0) if brake else 0.0,
                          "255,59,48"),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(gauge(str(gear) if gear is not None else "—",
                          "GEAR", gear / 8.0 if gear else 0.0,
                          "52,199,89"),
                    unsafe_allow_html=True)


def _telemetry_figure(tele: pd.DataFrame, driver_number: str | None = None) -> go.Figure:
    """SPEED / THROTTLE / BRAKE / GEAR / DELTA over one lap (synthetic feed)."""
    if driver_number and "driver_number" in tele:
        df = tele[tele["driver_number"] == driver_number]
    else:
        df = tele
    if df.empty:
        return _empty_figure("no telemetry feed")
    dist = df["distance_m"]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=dist, y=df["speed_kmh"], name="SPEED",
                             line=dict(width=2, color="rgb(114,179,255)"), fill="tozeroy",
                             fillcolor="rgba(114,179,255,0.12)"), secondary_y=False)
    fig.add_trace(go.Scatter(x=dist, y=df["throttle_pct"], name="THROTTLE",
                             line=dict(width=1.2, color="rgb(255,159,10)")), secondary_y=False)
    fig.add_trace(go.Scatter(x=dist, y=df["brake_pct"], name="BRAKE",
                             line=dict(width=1.2, color="rgb(255,59,48)")), secondary_y=False)
    if "gear" in df:
        fig.add_trace(go.Scatter(x=dist, y=df["gear"], name="GEAR",
                                 line=dict(width=1.2, color="rgb(52,199,89)")), secondary_y=False)
    if "delta_s" in df:
        fig.add_trace(go.Scatter(x=dist, y=df["delta_s"], name="DELTA",
                                 line=dict(width=1.8, dash="dot", color="rgb(232,235,240)")),
                      secondary_y=True)
    fig.update_yaxes(title_text="speed · throttle · brake · gear", secondary_y=False)
    fig.update_yaxes(title_text="delta (s)", secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="distance along lap (normalized)")
    fig.update_layout(**_layout(height=300))
    return fig


def _lap_pace_figure(laps: pd.DataFrame) -> go.Figure:
    """Real historical per-lap SPEED + DELTA from fastf1_laps."""
    df = laps.dropna(subset=["time_sec"]).copy()
    if df.empty:
        return _empty_figure("no lap data for this race")
    df["delta_s"] = df["time_sec"] - df["time_sec"].min()
    speed_cols = [c for c in ("speed_fl", "speed_i1", "speed_i2", "speed_trap") if c in df]
    df["speed_kmh"] = df[speed_cols].mean(axis=1) if speed_cols else np.nan
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df["lap"], y=df["speed_kmh"], name="SPEED",
                             line=dict(width=2, color="rgb(114,179,255)"),
                             fill="tozeroy", fillcolor="rgba(114,179,255,0.12)",
                             hovertemplate="lap %{x}<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=df["lap"], y=df["delta_s"], name="DELTA vs best",
                             line=dict(width=1.8, dash="dot", color="rgb(232,235,240)")),
                  secondary_y=True)
    fig.update_yaxes(title_text="speed (km/h)", secondary_y=False)
    fig.update_yaxes(title_text="delta (s)", secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="lap")
    fig.update_layout(**_layout(height=300))
    return fig


def _empty_figure(text: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=text, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(color="#8f95a0"))
    fig.update_layout(**_layout(showlegend=False, height=240))
    return fig


# ---------------------------------------------------------------------------
# Tyre strategy
# ---------------------------------------------------------------------------

def _stint_rows_from_stints(stints: pd.DataFrame, lb: pd.DataFrame | None) -> list[dict]:
    if stints is None or stints.empty:
        return []
    lb = lb if lb is not None and not lb.empty else pd.DataFrame()
    order = list(lb["driver_number"].astype(str)) if not lb.empty else []
    labels = {}
    if not lb.empty:
        labels = {str(r["driver_number"]): str(r.get("name_acronym") or r.get("driver") or "?")
                  for _, r in lb.iterrows()}
    rows = []
    for _, s in stints.iterrows():
        num = str(s.get("driver_number"))
        start = float(s.get("lap_start") or 1)
        raw_end = s.get("lap_end")
        if raw_end is not None and pd.notna(raw_end):
            end = float(raw_end)
        else:
            end = start + float(s.get("stint_length") or 30)
        rows.append({
            "driver": labels.get(num, num),
            "start": start,
            "end": max(end, start + 1),
            "compound": str(s.get("compound", "UNKNOWN")).upper(),
        })
    return rows


def _stint_rows_from_laps(laps: pd.DataFrame, top: int = 10) -> list[dict]:
    if laps is None or laps.empty or "compound" not in laps:
        return []
    df = laps.dropna(subset=["stint", "lap", "compound"]).copy()
    if df.empty:
        return []
    navg = df.groupby("driverId")["time_sec"].mean()
    order = list(navg.sort_values().index[:top])
    rows = []
    for did in order:
        d = df[df["driverId"] == did]
        driver = d["driver"].iloc[0]
        for stint, g in d.groupby("stint"):
            rows.append({
                "driver": driver,
                "start": float(g["lap"].min()),
                "end": float(g["lap"].max()),
                "compound": g["compound"].iloc[0].upper(),
            })
    return rows


def _tyre_figure(rows: list[dict]) -> go.Figure:
    """Horizontal stacked stint bars per driver, colored by compound."""
    if not rows:
        return _empty_figure("no stint data")
    legend_added: set[str] = set()
    fig = go.Figure()
    for r in rows:
        start = r["start"]
        length = r.get("length") or max(r["end"] - start + 1, 0.001)
        compound = r["compound"]
        show = compound not in legend_added
        legend_added.add(compound)
        fig.add_trace(go.Bar(
            y=[r["driver"]], x=[length], base=[start],
            orientation="h",
            marker=dict(color=_COMPOUND_COLOURS.get(compound, "#8f95a0"),
                        line=dict(color="#0b0d10", width=0.8)),
            customdata=[[compound, r["start"], r["end"]]],
            hovertemplate="%{y}<br>%{customdata[0]} laps %{customdata[1]}-%{customdata[2]}<extra></extra>",
            showlegend=show, name=compound, legendgroup=compound))
    fig.update_xaxes(title_text="race lap")
    fig.update_layout(**_layout(barmode="stack", height=300, hovermode="y"))
    fig.update_yaxes(autorange="reversed")
    return fig


# ---------------------------------------------------------------------------
# Timing panel
# ---------------------------------------------------------------------------

def _timing_panel_html(df: pd.DataFrame, position_col: str, name_col: str,
                       gap_col: str | None = None, colour_col: str | None = None,
                       gap_unit: str = "s", n: int = 4) -> str:
    if df is None or df.empty:
        return '<div class="skeuo-panel">' + intel_label("TIMING") + \
               '<div class="skeuo-value">NO TIMING</div></div>'
    body = ""
    for _, row in df.head(n).iterrows():
        pos = int(row[position_col])
        name = str(row[name_col])
        colour = str(row[colour_col]) if colour_col and colour_col in row.index and pd.notna(row[colour_col]) else "#8f95a0"
        gap = ""
        if gap_col and gap_col in row.index and pd.notna(row.get(gap_col)):
            try:
                gap = f"{float(row[gap_col]):+.1f}{gap_unit}"
            except (TypeError, ValueError):
                gap = str(row[gap_col])
        body += intel_row(f"P{pos}", name, gap, colour)
    return '<div class="skeuo-panel">' + intel_label("TIMING") + body + "</div>"


def _gap_column(lb: pd.DataFrame) -> str | None:
    if lb is None or lb.empty:
        return None
    for c in ("gap_to_leader", "interval", "gap"):
        if c in lb.columns and lb[c].notna().any():
            return c
    return None


# ---------------------------------------------------------------------------
# Coach / assistant panel
# ---------------------------------------------------------------------------

def _driver_id_from_code(code: str | None) -> int | None:
    if not code:
        return None
    try:
        df = query("SELECT driverId FROM drivers WHERE code = ?", {"1": code})
    except DataNotFoundError:
        return None
    return int(df.iloc[0]["driverId"]) if not df.empty else None


def _latest_race_id(hint: str | None) -> int | None:
    if not db_available():
        return None
    try:
        races = _races_with_circuit()
    except DataNotFoundError:
        return None
    if races.empty:
        return None
    if hint:
        h = str(hint).strip().lower()
        mask = (
            races["circuit"].str.lower().str.contains(h, regex=False)
            | races["location"].str.lower().str.contains(h, regex=False)
            | races["country"].str.lower().str.contains(h, regex=False)
        )
        races = races[mask]
    return int(races.iloc[-1]["raceId"]) if not races.empty else None


def _coach_panel(snap, hint_circuit: str | None) -> None:
    st.markdown(intel_label("AI DRIVER COACH"), unsafe_allow_html=True)
    report = live_coach_from_snapshot(snap)
    for f in report.findings:
        st.markdown(f"- **{f.area}** ({f.confidence:.0%}): {f.text}", unsafe_allow_html=True)
    if report.warnings:
        for w in report.warnings:
            st.caption(w)

    codes = [""]
    if snap.leaderboard is not None and not snap.leaderboard.empty:
        codes += [str(x) for x in snap.leaderboard["name_acronym"].dropna().unique()]
    focus = st.selectbox("Focus driver (lap-level)", codes, key="intel_focus",
                         format_func=lambda c: c or "leader")
    col_analyze, col_ask = st.columns(2)
    if col_analyze.button("Analyze Lap", key="intel_analyze"):
        code = focus or (str(snap.leaderboard.iloc[0].get("name_acronym") or "")
                         if snap.leaderboard is not None and not snap.leaderboard.empty else "")
        did = _driver_id_from_code(code)
        rid = _latest_race_id(hint_circuit)
        if did is None or rid is None:
            st.warning("Analyze Lap needs fastf1_laps telemetry (f1.db) + a driver code.")
        else:
            try:
                st.markdown(coach_race(rid, did).markdown())
            except DataNotFoundError as exc:
                st.info(str(exc))
            except Exception as exc:  # noqa: BLE001
                log_error("intel analyze lap failed: %s", exc)
                st.error(f"Analyze failed: {type(exc).__name__}")
    if col_ask.button("Ask AI", key="intel_ask"):
        if "intel_question" in st.session_state and st.session_state["intel_question"].strip():
            q = st.session_state["intel_question"]
            try:
                ans = ask(q, snapshot=snap, llm=LLMClient())
                st.markdown(ans.answer)
                st.caption(f"mode={ans.mode} · tools={', '.join(ans.tools_used) or 'none'} · "
                           f"audit={ans.audit_id}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Assistant failed: {type(exc).__name__}")
        else:
            st.info("Type a question below, then press Ask AI.")
    st.text_input("Ask the coach about this race...", key="intel_question")


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def _live_section() -> None:
    choices = ("openf1", "mock", "replay")
    current = st.session_state.get("provider", config.LIVE_PROVIDER)
    if current in ("mock", "replay") and "provider_sel" not in st.session_state:
        st.session_state["provider_sel"] = current
    provider = st.selectbox(
        "Provider", choices,
        index=choices.index(current) if current in choices else 0,
        key="provider_sel")
    st.session_state["provider"] = provider
    snap, err = _live_snapshot()
    if err or snap is None:
        st.warning(f"No live feed: {err or 'no snapshot'}")
        st.info("Switch the Provider dropdown above to **mock** for an offline demo.")
        return
    circuit_hint = snap.session.get("circuit_short_name")
    corners = _corners_for_circuit(circuit_hint)
    lb = snap.leaderboard
    tele = _live_telemetry(snap)

    hero(
        title="LIVE RACE",
        subtitle=f"{snap.session.get('session_name', 'Race')} · "
                 f"{circuit_hint or ''} · fetched {snap.fetched_at} · "
                 f"age {snap.age_seconds:.0f}s"
                 + (" · LIVE" if snap.is_live else " · OFFLINE / LAST KNOWN"),
        ticker=[f"POS {int(v)}" for v in (
            lb["position"].head(8).tolist() if lb is not None and "position" in lb else [])]
            or ["RACING", "PIT LANE", "GARAGE"],
        live=bool(snap.is_live),
    )
    if snap.is_live:
        st.success("RACE IN PROGRESS")
    else:
        st.info("Not currently live (offline/last known).")
    for w in snap.warnings:
        st.caption(f"{led('amber')} {w}")

    col_timing, col_map, col_tele = st.columns([1.05, 2.3, 1.05], gap="medium")
    with col_timing:
        gap_col = _gap_column(lb)
        st.markdown(_timing_panel_html(lb, "position", "name_acronym",
                                       gap_col, "team_colour"),
                    unsafe_allow_html=True)
        if lb is not None and not lb.empty:
            leader = lb.iloc[0]
            team = leader.get("team_name", "")
            st.markdown(pod("LEADER", str(leader.get("name_acronym") or "?"),
                            "green"), unsafe_allow_html=True)
            st.caption(f"{team} · {len(lb)} cars tracked")
    with col_map:
        st.markdown(intel_label("TRACK MAP"), unsafe_allow_html=True)
        markers = None
        if snap.source == "mock":
            markers = _markers_from_leaderboard(lb, corners)
        fig = _track_figure(corners, markers)
        st.plotly_chart(fig, width="stretch")
        track_name = corners.attrs.get("circuit", circuit_hint or "unknown")
        if markers is not None:
            st.caption(f"Track: {track_name} · car markers approximate (mock demo).")
        else:
            st.caption(f"Track: {track_name} · live car locations need a car_data "
                       "feed (not enabled for this provider).")
    with col_tele:
        st.markdown(intel_label("TELEMETRY"), unsafe_allow_html=True)
        _gauges(snap)
        if tele.empty:
            st.caption("No telemetry feed - gauges fall back to latest lap speeds.")

    st.markdown(intel_label("SPEED / THROTTLE / BRAKE / GEAR / DELTA"), unsafe_allow_html=True)
    if not tele.empty:
        leader_no = str(lb.iloc[0]["driver_number"]) if lb is not None and not lb.empty else None
        st.plotly_chart(_telemetry_figure(tele, leader_no), width="stretch")
        st.caption("Synthetic telemetry from mock provider (not real timing).")
    else:
        rid = _latest_race_id(circuit_hint)
        laps = pd.DataFrame()
        if rid is not None:
            try:
                from f1_analytics.database import lap_pace_race
                laps = lap_pace_race(rid)
            except DataNotFoundError:
                laps = pd.DataFrame()
        if laps.empty:
            st.plotly_chart(_empty_figure("no telemetry feed for this session"), width="stretch")
            st.caption("Live telemetry is not polled for this provider; historical "
                       "per-lap pace is shown when a matching race exists in f1.db.")
        else:
            st.plotly_chart(_lap_pace_figure(laps), width="stretch")
            st.caption(f"Real per-lap pace from fastf1_laps (race {rid}) - speed + delta vs best.")

    col_tyre, col_coach = st.columns(2, gap="medium")
    with col_tyre:
        st.markdown(intel_label("TYRE STRATEGY"), unsafe_allow_html=True)
        rows = _stint_rows_from_stints(snap.stints, lb)
        if rows:
            compounds = sorted({r["compound"] for r in rows})
            chips = "".join(intel_chip(c) for c in compounds)
            st.markdown(chips, unsafe_allow_html=True)
            st.plotly_chart(_tyre_figure(rows), width="stretch")
        else:
            st.plotly_chart(_empty_figure("no stint data"), width="stretch")
            st.caption("Stints come from the live feed; unavailable for this provider.")
    with col_coach:
        _coach_panel(snap, circuit_hint)


def _historical_section() -> None:
    try:
        races = _races_with_circuit()
    except DataNotFoundError as exc:
        st.error(str(exc))
        return
    if races.empty:
        st.error("No race calendar found.")
        return
    years = sorted(races["year"].unique())
    year = st.selectbox("Season", years, index=len(years) - 1, key="intel_year")
    year_races = races[races["year"] == year]
    labels = year_races["round"].astype(str) + " · " + year_races["circuit"] + \
        " · " + year_races["event"].fillna("")
    round_idx = st.selectbox("Round", range(len(year_races)), index=len(year_races) - 1,
                             format_func=lambda i: labels.iloc[i], key="intel_round")
    row = year_races.iloc[round_idx]

    hero(
        title=f"{row['circuit']} {year}",
        subtitle=f"ROUND {int(row['round'])} · {row['event']} · "
                 f"{row['location']}, {row['country']} · HISTORICAL",
        ticker=[f"R{int(row['round'])}", str(year), row["circuitRef"], "HISTORICAL"],
        live=False,
    )

    try:
        results = race_results(race_id=int(row["raceId"]))
    except DataNotFoundError as exc:
        st.error(str(exc))
        return
    results = results.sort_values("position")
    corners = _corners_for_race(int(row["raceId"]))

    from f1_analytics.database import lap_pace_race
    try:
        laps = lap_pace_race(int(row["raceId"]))
    except DataNotFoundError:
        laps = pd.DataFrame()

    col_timing, col_map, col_tele = st.columns([1.05, 2.3, 1.05], gap="medium")
    with col_timing:
        st.markdown(_timing_panel_html(
            results, "position", "driver", "points", gap_unit=" pts"),
            unsafe_allow_html=True)
        st.markdown(pod("RACE", f"{row['event']} · {len(results)} finishers", "green"),
                    unsafe_allow_html=True)
    with col_map:
        st.markdown(intel_label("TRACK MAP"), unsafe_allow_html=True)
        st.plotly_chart(_track_figure(corners), width="stretch")
        st.caption(f"Geometry from circuit_corners · {'f1.db' if not corners.empty else 'no corners stored'}")
    with col_tele:
        st.markdown(intel_label("TELEMETRY"), unsafe_allow_html=True)
        if not laps.empty and "time_sec" in laps:
            best = float(laps["time_sec"].min())
            steps = laps["speed_trap"].dropna()
            speed = float(steps.max()) if not steps.empty else 0.0
            st.markdown(gauge(f"{speed:.0f}", "SPEED · km/h", speed / 360.0, "114,179,255"),
                        unsafe_allow_html=True)
            st.markdown(gauge(f"{best:.1f}", "BEST LAP · s", 1.0, "52,199,89"),
                        unsafe_allow_html=True)
        else:
            st.markdown(gauge("—", "NO TELEMETRY", 0.0), unsafe_allow_html=True)
            st.caption("fastf1_laps required (f1.db).")

    st.markdown(intel_label("SPEED / DELTA per lap"), unsafe_allow_html=True)
    if not laps.empty:
        st.plotly_chart(_lap_pace_figure(laps), width="stretch")
        st.caption("Real per-lap speed + delta vs race best lap (fastf1_laps).")
    else:
        st.plotly_chart(_empty_figure("no lap data for this race"), width="stretch")

    col_tyre, col_coach = st.columns(2, gap="medium")
    with col_tyre:
        st.markdown(intel_label("TYRE STRATEGY"), unsafe_allow_html=True)
        trows = _stint_rows_from_laps(laps, top=10) if not laps.empty else []
        if trows:
            compounds = sorted({r["compound"] for r in trows})
            st.markdown("".join(intel_chip(c) for c in compounds), unsafe_allow_html=True)
            st.plotly_chart(_tyre_figure(trows), width="stretch")
        else:
            st.plotly_chart(_empty_figure("no stint data"), width="stretch")
    with col_coach:
        st.markdown(intel_label("AI DRIVER COACH"), unsafe_allow_html=True)
        if not laps.empty:
            codes = sorted(laps["code"].dropna().unique().tolist())
            driver = st.selectbox("Driver", codes, key="intel_hist_focus")
            did = _driver_id_from_code(driver)
            if did is not None:
                try:
                    st.markdown(coach_race(int(row["raceId"]), did).markdown())
                except DataNotFoundError as exc:
                    st.info(str(exc))
                except Exception as exc:  # noqa: BLE001
                    log_error("historical coach failed: %s", exc)
                    st.error(f"Coach failed: {type(exc).__name__}")
        else:
            st.info("Coach needs fastf1_laps (f1.db) for this race.")


def _coach_section() -> None:
    st.markdown(intel_label("AI DRIVER COACH · POST-SESSION"), unsafe_allow_html=True)
    st.caption("Numerical, evidence-based recommendations from f1.db lap data "
               "(2018+). Never coaches on incomplete/incomparable data.")
    try:
        from f1_analytics.database import driver_list
        drivers = driver_list()
        if drivers.empty:
            st.info("No driver list available.")
            return
        driver_id = st.selectbox(
            "Driver", [None, *drivers["driverId"].tolist()],
            format_func=lambda v: "select a driver" if v is None else '{} ({})'.format(
                drivers.loc[drivers["driverId"] == v, "forename"].iloc[0] + " " +
                drivers.loc[drivers["driverId"] == v, "surname"].iloc[0], v),
            key="intel_coach_driver")
        if driver_id is not None:
            from f1_analytics.coach import coach_laps
            st.markdown(coach_laps(driver_id=int(driver_id)).markdown())
    except DataNotFoundError as exc:
        st.warning(f"Coach unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001
        log_error("coach section failed: %s", exc)
        st.error(f"Coach unavailable: {type(exc).__name__}")


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def page_race_intel() -> None:
    st.markdown(intel_label("RACE INTELLIGENCE"), unsafe_allow_html=True)
    mode = st.radio("Mode", _MODES, horizontal=True, label_visibility="collapsed",
                    key="intel_mode")
    if mode == "LIVE RACE":
        _live_section()
    elif mode == "HISTORICAL":
        _historical_section()
    else:
        _coach_section()