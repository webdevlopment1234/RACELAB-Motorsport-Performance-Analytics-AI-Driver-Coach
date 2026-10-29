"""Shared live-provider UI helpers (LIVE page + Race Intelligence)."""

from __future__ import annotations

import streamlit as st

from f1_analytics.live import list_replays


def replay_snapshot_picker() -> None:
    """Selectbox over saved replay snapshots; stores the path in session state.

    Shows actionable guidance when dataset/live_replays has no files yet.
    """
    replays = list_replays()
    if not replays:
        st.session_state.pop("replay_path", None)
        st.warning(
            "Provider 'replay' has no saved snapshots yet. Start a session "
            "with **openf1** (or **mock** for an offline demo), press "
            "**Save snapshot as replay**, then switch back to replay.")
        return
    labels = [f"{p.stem}" for p in replays]
    current = st.session_state.get("replay_path")
    idx = next((i for i, p in enumerate(replays) if str(p) == current), 0)
    choice = st.selectbox("Replay snapshot", labels, index=idx, key="replay_sel")
    st.session_state["replay_path"] = str(replays[labels.index(choice)])
