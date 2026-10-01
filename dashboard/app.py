"""F1 Analytics Streamlit dashboard (Phase 5).

Run:  streamlit run dashboard/app.py   (fully functional offline)
Pages: Analytics, Race Intelligence, Drivers, Constructors, Circuits, LIVE,
       Predictions, Coach, Assistant, Data Health.

Design rules:
- Blocking problems -> st.error with the exact recovery command.
- Optional-feature unavailability -> st.warning.
- Normal empty states -> st.info.
- Programming bugs must not be hidden: unexpected exceptions are logged
  with the full traceback and shown in an expander.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # dashboard/ (reusable skin)

import streamlit as st  # noqa: E402

from skin import apply_skin, gauge, hero, led, pod  # noqa: E402

from f1_analytics import config  # noqa: E402
from f1_analytics.analytics import (  # noqa: E402
    circuit_analytics_table,
    constructor_summary_table,
    driver_summary_table,
)
from f1_analytics.assistant import LLMClient, ask  # noqa: E402
from f1_analytics.coach import coach_laps  # noqa: E402
from f1_analytics.database import data_source, query, race_calendar, race_results  # noqa: E402
from f1_analytics.data import DataNotFoundError, asset_status  # noqa: E402
from f1_analytics.features import feature_audit  # noqa: E402
from f1_analytics.live import create_provider  # noqa: E402
from f1_analytics.logging_utils import log_error  # noqa: E402
from f1_analytics.models import FeatureSchemaError, ModelArtifactError, models_status, predict_df, predictor  # noqa: E402
from f1_analytics.preprocessing import validation_summary  # noqa: E402

from intel import page_race_intel  # noqa: E402

PAGES = ("Analytics", "Race Intelligence", "Drivers", "Constructors", "Circuits",
         "LIVE", "Predictions", "Coach", "Assistant", "Data Health")

st.set_page_config(page_title="RACELAB F1 Analytics", layout="wide")


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
    except Exception as exc:  # noqa: BLE001 - live page must never crash
        log_error("live provider error: %s", exc)
        return None, f"{name} unavailable: {exc}"


def _render_df(df, height=420):
    import plotly.express as px
    if df is None or df.empty:
        st.info("No data available for this selection.")
        return
    st.dataframe(df, width="stretch", height=height)


def _sidebar_status():
    src = data_source()
    st.sidebar.markdown(
        f"{led('green' if src['mode'] == 'sqlite' else 'amber')}"
        f"<b>DATA STATUS</b>",
        unsafe_allow_html=True)
    if src["mode"] == "sqlite":
        st.sidebar.info("Querying f1.db (full historical + telemetry).")
    else:
        st.sidebar.warning("f1.db missing - CSV fallback mode (1950-2024).")
        st.sidebar.caption(src["note"])
    missing = [a for a in asset_status().values() if not a.ok]
    if missing:
        for asset in missing:
            st.sidebar.markdown(
                f"{led('red')}{asset.name} <small>missing</small>",
                unsafe_allow_html=True)
            if asset.fix:
                st.sidebar.caption(asset.fix)
        if st.sidebar.button("Copy data-status command"):
            st.code("f1-analytics data-status", language="text")


def page_analytics():
    cal = race_calendar()
    if cal.empty:
        st.error("No race data found. f1.db is missing and the CSV fallback "
                 "returned nothing.\nRun `f1-analytics data-status` for help.")
        return
    years = sorted(cal["year"].unique())
    year = st.selectbox("Season", years, index=len(years) - 1)
    results = race_results(year=year)
    hero(
        title=f"SEASON {year}",
        subtitle="HISTORICAL ANALYTICS · FAST LAPS · CHAMPIONSHIP RACES",
        ticker=[f"{year}", "RACELAB", "DATA CORE ONLINE", "PARALLAX ENGAGED"],
        live=False,
    )
    if results is not None and not results.empty:
        rounds = int(results["round"].nunique())
        n_pts = int(results["points"].fillna(0).sum())
        top = results["driver"].value_counts().idxmax()
        p1 = int((results["status"] == "Finished") .sum()) if "status" in results.columns else 0
        c1, c2, c3, c4 = st.columns(4)
        pods = [
            pod("ROUNDS", rounds, "green"),
            pod("POINTS AWARDED", n_pts, "amber"),
            pod("GRID LEADER", top, "blue"),
            pod("FINISHERS", p1, "green"),
        ]
        for col, p in zip((c1, c2, c3, c4), pods):
            with col:
                st.markdown(p, unsafe_allow_html=True)
    st.subheader(f"Race results {year}")
    cols = [c for c in ("round", "driver", "constructor", "grid", "position", "points", "status")
            if c in results.columns]
    _render_df(results[cols] if cols else results)
    src = data_source()
    st.caption(f"Data: {src['mode']} · {len(results)} driver results · reference at "
               f"`{config.F1_DB_PATH}`" + (f" · {src['note']}" if src["note"] else ""))


def page_drivers():
    st.header("Driver Analytics")
    try:
        df = _driver_table_cache()
    except DataNotFoundError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        log_error("driver analytics failed: %s", exc)
        st.error(f"Driver analytics failed unexpectedly: {type(exc).__name__}")
        _show_traceback(exc)
        return
    if df is None or df.empty:
        st.error("Driver analytics unavailable - no data returned "
                 "(f1.db missing and CSV fallback empty?).")
    else:
        _render_df(df)


def page_constructors():
    st.header("Constructor Analytics")
    try:
        df = _constructor_cache()
    except DataNotFoundError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        log_error("constructor analytics failed: %s", exc)
        st.error(f"Constructor analytics failed unexpectedly: {type(exc).__name__}")
        _show_traceback(exc)
        return
    if df is None or df.empty:
        st.error("Constructor analytics unavailable - no data returned.")
    else:
        _render_df(df)


def page_circuits():
    st.header("Circuit Explorer")
    try:
        df = _circuit_cache()
    except DataNotFoundError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        log_error("circuit analytics failed: %s", exc)
        st.error(f"Circuit analytics failed unexpectedly: {type(exc).__name__}")
        _show_traceback(exc)
        return
    if df is None or df.empty:
        st.error("Circuit analytics unavailable - no data returned.")
        return
    _render_df(df)


def page_live():
    provider = st.selectbox("Provider", ["openf1", "mock", "replay"],
                            index=0, key="provider_sel")
    if "provider" not in st.session_state or st.session_state["provider"] != provider:
        st.session_state["provider"] = provider
    snap, err = _live_with_error_handling()
    if err:
        hero(
            title="LIVE SESSION",
            subtitle="OFFLINE · LIVE FEED UNAVAILABLE",
            ticker=[f"SIGNAL {err}", "TRY PROVIDER: MOCK / REPLAY"],
            live=False,
        )
        st.warning(f"No live feed: {err}")
        st.info("Switch the Provider dropdown above to **mock** for an offline demo, "
                "or **replay** for a saved session. Live timing is optional - "
                "all historical pages stay fully functional.")
        return
    hero(
        title=f"{snap.session.get('session_name', 'LIVE SESSION')}",
        subtitle=f"{snap.session.get('circuit_short_name', '')} · "
                 f"fetched {snap.fetched_at} · age {snap.age_seconds:.0f}s"
                 + (" · LIVE" if snap.is_live else " · OFFLINE / LAST KNOWN"),
        ticker=[f"POS {int(v)}" for v in
                (snap.leaderboard["position"].head(6).tolist()
                 if snap.leaderboard is not None and "position" in snap.leaderboard.columns
                 else [])] or ["RACING", "PIT LANE", "GARAGE"],
        live=bool(snap.is_live),
    )
    if snap.is_live:
        st.success("RACE IN PROGRESS")
    else:
        st.info("Not currently live (offline/last known).")
    st.subheader(f"{snap.session.get('session_name', 'Session')} · "
                 f"{snap.session.get('circuit_short_name', '')}")

    lb = snap.leaderboard
    if lb is not None and not lb.empty:
        gap_col, board_col = st.columns([1, 3], gap="medium")
        with gap_col:
            gap_val = None
            for gcol in ("gap", "gap_to_leader", "time_gap"):
                if gcol in lb.columns and lb[gcol].notna().any():
                    gap_val = lb[gcol].bfill().iloc[0]
                    break
            if gap_val is not None:
                try:
                    fgap = float(gap_val)
                    pct = min(1.0, fgap / 30.0) if fgap >= 0 else 0.1
                    st.markdown(gauge(f"{fgap:+.1f}", "GAP TO LEADER", pct),
                                unsafe_allow_html=True)
                except (TypeError, ValueError):
                    pass
            leader = lb.iloc[0]
            leader_row = (leader.get("name_acronym")
                          or leader.get("driver")
                          or str(leader.get("position", "?")))
            st.markdown(pod("LEADER", str(leader_row), "green"), unsafe_allow_html=True)
        with board_col:
            st.subheader("Leaderboard")
            _render_df(lb, height=300)
    else:
        st.info("Leaderboard empty (no data yet or interval 404).")

    tab_w, tab_lap, tab_rc = st.tabs(["Weather", "Latest Laps", "Race Control"])
    with tab_w:
        if snap.weather is not None and not snap.weather.empty:
            _render_df(snap.weather)
        else:
            st.info("No weather samples.")
    with tab_lap:
        if snap.latest_laps is not None and not snap.latest_laps.empty:
            _render_df(snap.latest_laps)
        else:
            st.info("No lap samples.")
    with tab_rc:
        if snap.race_control is not None and not snap.race_control.empty:
            _render_df(snap.race_control)
        else:
            st.info("No race-control messages.")

    if st.toggle("Auto-refresh (>=5s)", value=False):
        st.rerun(seconds=max(5.0, float(config.OPENF1_POLL_SECONDS)))


def _show_traceback(exc: Exception) -> None:
    with st.expander("Technical details (for maintainers)"):
        st.code(traceback.format_exc(), language="text")


def page_predictions():
    st.header("Race Predictions")
    st.caption("Leakage-safe inputs at POST-QUALIFYING; probabilities are estimates, "
               "not guarantees. Chronological split: train <=2022, val 2023-24, test 2025.")

    # 1) Training table must exist (models need it).
    from f1_analytics.features import training_table
    try:
        df = training_table()
    except DataNotFoundError as exc:
        st.error(str(exc))
        st.code("f1-analytics data-status", language="text")
        return
    except Exception as exc:  # noqa: BLE001
        log_error("training table load failed: %s", exc)
        st.error(f"Could not load the training table: {type(exc).__name__}: {exc}")
        _show_traceback(exc)
        return

    # 2) Models must exist, load, and match the current feature schema.
    status = models_status()
    if not status["ok"]:
        bad = [t for t, i in status["models"].items() if not i["ok"]]
        st.error(f"Prediction unavailable: model artifacts not ready "
                 f"(missing/incompatible: {', '.join(bad)}).")
        with st.expander("Model readiness detail"):
            for task, info in status["models"].items():
                mark = "ok" if info["ok"] else "FAIL"
                st.markdown(f"- **{task}** [{mark}]: {info['error'] or 'ready'}")
        st.code("f1-analytics train", language="text")
        return

    # 3) Feature rows to score.
    if "year" not in df.columns:
        st.error("Training table has no 'year' column - schema mismatch. "
                 "Re-generate training_dataset.parquet.")
        return
    year = st.selectbox("Season (feature rows)", sorted(df["year"].unique()),
                        index=len(df["year"].unique()) - 1)
    rows = df[df["year"] == year]
    if rows.empty:
        st.info("No feature rows for that year.")
        return
    st.caption(f"{len(rows)} feature rows for {year} (e.g. grid paces by driver).")
    try:
        driver_codes = query(
            "SELECT d.driverId, d.code FROM drivers d WHERE d.driverId IN "
            f"({','.join('?' for _ in rows['driverId'].unique())})",
            {str(i): v for i, v in enumerate(rows["driverId"].unique())},
        ) if not rows.empty else None
    except DataNotFoundError as exc:
        st.warning(f"Could not resolve driver codes: {exc}")
        driver_codes = None
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

    # 4) Score each task; per-task failures are isolated and actionable.
    for task in ("finish", "is_dnf", "is_podium", "is_winner"):
        try:
            artifact = predictor(task)
            valid, problems = artifact.validate()
            if not valid:
                st.error(f"**{task}**: artifact invalid ({'; '.join(problems)}). "
                         "Re-train with `f1-analytics train`.")
                continue
            out = predict_df(artifact, record.to_frame().T)
            st.markdown(f"**{task}** -> {out.iloc[0].to_dict()}")
            st.caption(f"model {artifact.data_version} · split {artifact.split} · "
                       f"inputs={len(artifact.input_columns)}")
        except (ModelArtifactError, FeatureSchemaError) as exc:
            st.error(f"**{task}**: {exc}")
        except Exception as exc:  # noqa: BLE001
            log_error("prediction failed for task %s: %s", task, exc)
            st.error(f"**{task}** failed unexpectedly: {type(exc).__name__}")
            _show_traceback(exc)


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
        def _driver_label(v) -> str:
            if v is None:
                return "— select driver —"
            name = driver_rows.loc[driver_rows["driverId"] == v, "driver"].iloc[0]
            return str(name)

        driver_id = st.selectbox(
            "Driver", [None, *list(driver_rows["driverId"])],
            format_func=_driver_label,
            index=0)
        if driver_id is not None:
            report = coach_laps(driver_id=int(driver_id))
            st.markdown(report.markdown())
    except DataNotFoundError as exc:
        st.warning(f"Coach lap analysis unavailable: {exc}")
        st.caption("Coach telemetry (fastf1_laps) only exists inside f1.db - it is "
                   "not part of the CSV fallback.")
    except Exception as exc:  # noqa: BLE001
        log_error("coach failed: %s", exc)
        st.error(f"Coach unavailable: {type(exc).__name__}")
        _show_traceback(exc)
    st.caption(f"Drivers available: {n}.")


def page_assistant():
    st.header("Race Assistant")
    llm = LLMClient()
    mode = "enabled (key + openai installed)" if llm.available else "RULE-BASED fallback"
    st.caption(f"LLM mode: {mode}. Without a key the assistant uses deterministic "
               "rule-based answers from validated local/live data.")
    q = st.text_area("Ask about drivers, circuits, constructors, live standings, or coaching:",
                     height=80)
    col1, col2 = st.columns([3, 1])
    go = col1.button("Ask")
    if col2.button("Clear"):
        st.session_state.pop("answer", None)
        st.rerun()
    if go and q.strip():
        try:
            snap, _ = _live_with_error_handling()
            ans = ask(q, snapshot=snap, llm=llm)
            st.session_state["answer"] = ans
        except Exception as exc:  # noqa: BLE001 - assistant must never crash the page
            log_error("assistant failed: %s", exc)
            st.error(f"Assistant failed unexpectedly: {type(exc).__name__}")
    if st.session_state.get("answer"):
        ans = st.session_state["answer"]
        st.markdown(ans.answer)
        st.caption(f"mode={ans.mode} · tools={', '.join(ans.tools_used) or 'none'} · "
                   f"evidence={', '.join(ans.evidence_keys) or 'none'} · audit={ans.audit_id}")


def page_data_health():
    st.header("Data Health")
    missing = [a for a in asset_status().values() if not a.ok]
    if missing:
        st.warning("Missing data files:")
        for asset in missing:
            st.markdown(f"- **{asset.name}** ({asset.path})")
            if asset.fix:
                st.markdown(f"  - {asset.fix}")
        st.code("f1-analytics data-status", language="text")
    with st.spinner("Running validation..."):
        reports = validation_summary()
    for report in reports:
        st.subheader(report["source"])
        st.text(report["summary"])
        st.dataframe(report["checks"], width="stretch")
    st.caption("Known coverage limits: CSV ends 2024 · fastf1_laps starts 2018 · "
               "tracks.yaml 24/32 · 2026 partial season · OpenF1 history 2023+")
    st.text("Feature audit contract view:")
    try:
        _render_df(feature_audit())
    except Exception as exc:  # noqa: BLE001
        log_error("feature audit failed: %s", exc)
        st.error(f"Feature audit unavailable: {type(exc).__name__}")


def main():
    apply_skin()
    st.sidebar.title("")  # RACELAB wordmark is painted by the skin ::before
    page = st.sidebar.radio("Page", PAGES)
    st.sidebar.caption(f"package v0.1.0 · live default {config.LIVE_PROVIDER}")
    _sidebar_status()
    page_handlers = {
        "Analytics": page_analytics,
        "Race Intelligence": page_race_intel,
        "Drivers": page_drivers,
        "Constructors": page_constructors,
        "Circuits": page_circuits,
        "LIVE": page_live,
        "Predictions": page_predictions,
        "Coach": page_coach,
        "Assistant": page_assistant,
        "Data Health": page_data_health,
    }
    handler = page_handlers[page]
    try:
        handler()
    except DataNotFoundError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the dashboard alive
        log_error("unhandled dashboard error on %s: %s", page, exc)
        st.error(f"Unexpected error on the '{page}' page: {type(exc).__name__} - "
                 "the rest of the dashboard keeps working.")
        _show_traceback(exc)


if __name__ == "__main__":
    main()