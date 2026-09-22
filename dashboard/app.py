"""F1 Analytics Streamlit dashboard (Phase 5).

Run:  streamlit run dashboard/app.py   (fully functional offline)
Pages: Analytics, Drivers, Constructors, Circuits, LIVE, Predictions,
       Coach, Assistant, Data Health.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from f1_analytics import config  # noqa: E402
from f1_analytics.analytics import (  # noqa: E402
    circuit_analytics_table,
    constructor_summary_table,
    driver_summary_table,
)
from f1_analytics.assistant import LLMClient, ask  # noqa: E402
from f1_analytics.coach import coach_laps, live_coach_from_snapshot  # noqa: E402
from f1_analytics.database import lap_pace, query, race_calendar, race_results, standings_driver  # noqa: E402
from f1_analytics.features import feature_audit  # noqa: E402
from f1_analytics.live import create_provider  # noqa: E402
from f1_analytics.models import predict_df, predictor  # noqa: E402
from f1_analytics.preprocessing import validation_summary  # noqa: E402
from f1_analytics.simulation import simulate  # noqa: E402

PAGES = ("Analytics", "Drivers", "Constructors", "Circuits", "LIVE",
         "Predictions", "Coach", "Assistant", "Data Health")

st.set_page_config(page_title="F1 Analytics Platform", layout="wide")


@st.cache_resource(show_spinner=False)
def _driver_table_cache() -> object:
    return driver_summary_table()


@st.cache_resource(show_spinner=False)
def _constructor_cache():
    return constructor_summary_table()


@st.cache_resource(show_spinner=False)
def _circuit_cache():
    return circuit_analytics_table()


@st.cache_resource(show_spinner=False)
def _provider_cache(name: str):
    return create_provider(name)


def _live_with_error_handling():
    """Return (snapshot, error_str). Never raises on offline providers."""
    try:
        name = st.session_state.get("provider", config.LIVE_PROVIDER)
        prov = _provider_cache(name)
        snap = prov.snapshot()
        if snap is None:
            return None, f"{name} returned no snapshot (offline)"
        return snap, ""
    except Exception as exc:  # noqa: BLE001
        return None, f"{name} unavailable: {exc}"


def _render_df(df, height=420):
    import plotly.express as px
    if df is None or df.empty:
        st.info("No data available for this selection.")
        return
    st.dataframe(df, use_container_width=True, height=height)


def page_analytics():
    st.header("Historical Analytics")
    cal = race_calendar()
    if cal.empty:
        st.error("f1.db not found - run with dataset present.")
        return
    years = sorted(cal["year"].unique())
    year = st.selectbox("Season", years, index=len(years) - 1)
    results = race_results(year=year)
    st.subheader(f"Race results {year}")
    cols = [c for c in ("round", "driver", "constructor", "grid", "position", "points", "status")
            if c in results.columns]
    _render_df(results[cols] if cols else results)
    st.caption(f"Data: f1.db · {len(results)} driver results · dataset reference at "
               f"`{config.F1_DB_PATH}`")


def page_drivers():
    st.header("Driver Analytics")
    df = _driver_table_cache()
    if df is not None and not df.empty:
        _render_df(df)
    else:
        st.error("Driver analytics unavailable (f1.db missing?).")


def page_constructors():
    st.header("Constructor Analytics")
    df = _constructor_cache()
    if df is not None and not df.empty:
        _render_df(df)
    else:
        st.error("Constructor analytics unavailable.")


def page_circuits():
    st.header("Circuit Explorer")
    df = _circuit_cache()
    if df is None or df.empty:
        st.error("Circuit analytics unavailable.")
        return
    _render_df(df)


def page_live():
    st.header("LIVE Session")
    provider = st.selectbox("Provider", ["openf1", "mock", "replay"],
                            index=0, key="provider_sel")
    if "provider" not in st.session_state or st.session_state["provider"] != provider:
        st.session_state["provider"] = provider
    snap, err = _live_with_error_handling()
    if err:
        st.warning(f"No live feed: {err}")
        st.info("LIVE page is optional - historical pages stay fully functional.")
        return
    st.subheader(f"{snap.session.get('session_name', 'Session')} · "
                 f"{snap.session.get('circuit_short_name', '')}")
    if snap.is_empty:
        st.info("No session data yet - upcoming/empty window. "
                "(OpenF1 notes: upcoming sessions return empty payloads.)")
    if snap.warnings:
        st.caption("; ".join(snap.warnings))
    st.caption(f"Source: {snap.source} · fetched {snap.fetched_at} · "
               f"age {snap.age_seconds:.0f}s · is_live={snap.is_live}")
    if snap.is_live:
        st.success("RACE IN PROGRESS")
    else:
        st.info("Not currently live (offline/last known).")

    lb = snap.leaderboard
    if lb is not None and not lb.empty:
        st.subheader("Leaderboard")
        _render_df(lb)
    else:
        st.info("Leaderboard empty (no data yet or interval 404).")

    tab_w, tab_lap, tab_rc = st.tabs(["Weather", "Latest Laps", "Race Control"])
    with tab_w:
        _render_df(snap.weather) if snap.weather is not None and not snap.weather.empty \
            else st.info("No weather samples.")
    with tab_lap:
        _render_df(snap.latest_laps) if snap.latest_laps is not None and not snap.latest_laps.empty \
            else st.info("No lap samples.")
    with tab_rc:
        _render_df(snap.race_control) if snap.race_control is not None and not snap.race_control.empty \
            else st.info("No race-control messages.")

    if st.toggle("Auto-refresh (>=5s)", value=False):
        st.rerun(seconds=max(5.0, float(config.OPENF1_POLL_SECONDS)))


def page_predictions():
    st.header("Race Predictions")
    st.caption("Leakage-safe inputs at POST-QUALIFYING; probabilities are estimates, "
               "not guarantees. Chronological split: train <=2022, val 2023-24, test 2025.")

    try:
        from f1_analytics.features import training_table
        df = training_table()
        year = st.selectbox("Season (feature rows)", sorted(df["year"].unique()),
                            index=len(df["year"].unique()) - 1)
        rows = df[df["year"] == year]
        if rows.empty:
            st.info("No feature rows for that year.")
            return
        st.caption(f"{len(rows)} feature rows for {year} (e.g. grid paces by driver).")
        driver_codes = query(
            "SELECT d.driverId, d.code FROM drivers d WHERE d.driverId IN "
            f"({','.join('?' for _ in rows['driverId'].unique())})",
            {str(i): v for i, v in enumerate(rows["driverId"].unique())},
        ) if not rows.empty else None
        if driver_codes is not None and not driver_codes.empty:
            rows = rows.merge(driver_codes, on="driverId", how="left")
        sample = st.selectbox(
            "Row to score",
            range(len(rows)),
            format_func=lambda i: rows.iloc[i].get("code", f"row {i}"),
        )
        record = rows.iloc[sample]
        st.write("Scoring row:")
        st.json(record.to_dict())
        for task in ("finish", "is_dnf", "is_podium", "is_winner"):
            artifact = predictor(task)
            out = predict_df(artifact, record.to_frame().T)
            st.markdown(f"**{task}** -> {out.iloc[0].to_dict()}")
            st.caption(f"model {artifact.data_version} · split {artifact.split} · "
                       f"inputs={len(artifact.input_columns)}")
    except Exception as exc:  # noqa: BLE001
        st.info(f"Model artifacts not trained yet: {exc}")
        st.code("python -c \"from f1_analytics.models import train_all_years; train_all_years()\"")


def page_coach():
    st.header("AI Driver Coach")
    st.caption("Numerical, evidence-based recommendations. Never coaches on "
               "incomplete/incomparable data.")
    n = 0
    try:
        driver_rows = query(
            "SELECT driverId, forename || ' ' || surname AS driver FROM drivers "
            "ORDER BY driverId LIMIT 500"
        )
        n = len(driver_rows)
        driver_id = st.selectbox(
            "Driver", [None, *list(driver_rows["driverId"])],
            format_func=lambda v: v if v is None else
            driver_rows.loc[driver_rows["driverId"] == v, "driver"].iloc[0],
            index=0)
        if driver_id is not None:
            report = coach_laps(driver_id=int(driver_id))
            st.markdown(report.markdown())
    except Exception as exc:  # noqa: BLE001
        st.error(f"Coach unavailable: {exc} (need f1.db + fastf1_laps)")
    st.caption(f"Drivers available: {n}.")


def page_assistant():
    st.header("Race Assistant")
    llm = LLMClient()
    st.caption(f"LLM mode: {'enabled (key present)' if llm.available else 'RULE-BASED fallback'}.")
    q = st.text_area("Ask about drivers, circuits, constructors, live standings, or coaching:",
                     height=80)
    col1, col2 = st.columns([3, 1])
    go = col1.button("Ask")
    if col2.button("Clear"):
        st.session_state.pop("answer", None)
        st.rerun()
    if go and q.strip():
        snap, _ = _live_with_error_handling()
        ans = ask(q, snapshot=snap, llm=llm)
        st.session_state["answer"] = ans
    if st.session_state.get("answer"):
        ans = st.session_state["answer"]
        st.markdown(ans.answer)
        st.caption(f"mode={ans.mode} · tools={', '.join(ans.tools_used) or 'none'} · "
                   f"evidence={', '.join(ans.evidence_keys) or 'none'} · audit={ans.audit_id}")


def page_data_health():
    st.header("Data Health")
    with st.spinner("Running validation..."):
        reports = validation_summary()
    for report in reports:
        st.subheader(report["source"])
        st.text(report["summary"])
        st.dataframe(report["checks"], use_container_width=True)
    st.caption("Known coverage limits: CSV ends 2024 · fastf1_laps starts 2018 · "
               "tracks.yaml 24/32 · 2026 partial season · OpenF1 history 2023+")
    st.text("Feature audit contract view:")
    _render_df(feature_audit())


def main():
    st.sidebar.title("F1 Analytics")
    page = st.sidebar.radio("Page", PAGES)
    st.sidebar.caption(f"package v0.1.0 · live default {config.LIVE_PROVIDER}")
    if page == "Analytics":
        page_analytics()
    elif page == "Drivers":
        page_drivers()
    elif page == "Constructors":
        page_constructors()
    elif page == "Circuits":
        page_circuits()
    elif page == "LIVE":
        page_live()
    elif page == "Predictions":
        page_predictions()
    elif page == "Coach":
        page_coach()
    elif page == "Assistant":
        page_assistant()
    elif page == "Data Health":
        page_data_health()


if __name__ == "__main__":
    main()