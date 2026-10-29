"use client";

import { useEffect, useState } from "react";

import DataTable from "@/components/DataTable";
import { ErrorNote, Findings, Panel, Pill } from "@/components/Panel";
import { api, type CoachReport, type Snapshot } from "@/lib/api";
import { usePoll } from "@/lib/useApi";

type Providers = { providers: string[]; active: string | null };
type Row = Record<string, unknown>;

export default function RaceIntelligencePage() {
  const [providers, setProviders] = useState<Providers>({ providers: ["openf1", "mock", "replay"], active: null });
  const [providersErr, setProvidersErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadProviders() {
    setProvidersErr(null);
    try {
      setProviders(await api<Providers>("/api/live/providers"));
    } catch (e) {
      setProvidersErr(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void loadProviders();
  }, []);

  const active = providers.active;
  const snap = usePoll<Snapshot>(active ? "/api/live/snapshot" : null, 5000);
  const coach = usePoll<CoachReport>(active ? "/api/live/coach" : null, 8000);

  async function start(provider: string) {
    setBusy(true);
    try {
      await api("/api/live/session", { method: "POST", body: JSON.stringify({ provider }) });
      await loadProviders();
    } catch (e) {
      setProvidersErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    try {
      await api("/api/live/session", { method: "DELETE" });
      await loadProviders();
    } finally {
      setBusy(false);
    }
  }

  async function saveReplay() {
    setBusy(true);
    try {
      await api("/api/live/save-snapshot", { method: "POST" });
      await loadProviders();
    } catch (e) {
      setProvidersErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function refreshNow() {
    setBusy(true);
    try {
      await api("/api/live/refresh", { method: "POST" });
      snap.reload();
      coach.reload();
    } finally {
      setBusy(false);
    }
  }

  const session = (snap.data?.session ?? {}) as Row;

  return (
    <>
      <h1 className="page-title">Race Intelligence</h1>
      <p className="page-sub">
        Live/historical race view: timing P1-P4, weather, race control, stints and tyre strategy with the AI coach.
      </p>

      <Panel
        title="Live session"
        right={
          active ? (
            <span className="row">
              <Pill status="info">{active}</Pill>
              {snap.data ? <Pill status={snap.data.is_live ? "ok" : "warn"}>{snap.data.is_live ? "live" : "not live"}</Pill> : null}
            </span>
          ) : (
            <Pill status="warn">no session</Pill>
          )
        }
      >
        {providersErr ? <ErrorNote message={providersErr} /> : null}
        {!active ? (
          <div className="row">
            {["openf1", "mock", "replay"].map((p) => (
              <button key={p} className={`btn ${p === "openf1" ? "primary" : ""}`} disabled={busy} onClick={() => start(p)}>
                Start {p}
              </button>
            ))}
            <span className="muted">
              openf1 = free live API (2023+, needs internet) | mock = offline demo | replay = last saved snapshot
            </span>
          </div>
        ) : (
          <div className="row">
            <button className="btn teal" disabled={busy} onClick={refreshNow}>Refresh now</button>
            <button className="btn" disabled={busy} onClick={saveReplay}>Save snapshot as replay</button>
            <button className="btn" disabled={busy} onClick={stop}>End session</button>
          </div>
        )}

        {active && snap.data ? (
          <div className="mt12">
            <span className="mono dim">
              source {snap.data.source} | fetched {new Date(snap.data.fetched_at).toLocaleTimeString()} | session{" "}
              {String(session["name"] ?? session["session_type"] ?? "-")}
            </span>
            {snap.data.warnings.length > 0 ? <div className="warn-note">{snap.data.warnings.join("; ")}</div> : null}
          </div>
        ) : null}
      </Panel>

      <div className="grid2">
        <Panel title="Leaderboard">
          {active ? <DataTable rows={snap.data?.leaderboard ?? []} /> : <p className="muted mt12 mb0">Start a session to see the live order.</p>}
        </Panel>
        <Panel title="Weather">
          {active ? <DataTable rows={snap.data?.weather ?? []} /> : <p className="muted mt12 mb0">No session.</p>}
        </Panel>
      </div>

      <div className="grid2">
        <Panel title="Race control">
          {active ? (
            <DataTable
              rows={snap.data?.race_control ?? []}
              columns={["date", "category", "flag", "message"]}
              maxRows={50}
            />
          ) : (
            <p className="muted mt12 mb0">No session.</p>
          )}
        </Panel>
        <Panel title="Intervals (gaps)">
          {active ? <DataTable rows={snap.data?.intervals ?? []} /> : <p className="muted mt12 mb0">No session.</p>}
        </Panel>
      </div>

      <Panel title="Stints - tyre strategy">
        {active ? <DataTable rows={snap.data?.stints ?? []} /> : <p className="muted mt12 mb0">No session.</p>}
      </Panel>

      <Panel title="AI driver coach - live">
        {active ? (
          coach.data ? (
            <>
              <Findings findings={coach.data.findings} warnings={coach.data.warnings} />
            </>
          ) : (
            <p className="muted mt12 mb0">No live coach report yet.</p>
          )
        ) : (
          <p className="muted mt12 mb0">Start a session to get live coaching.</p>
        )}
      </Panel>
    </>
  );
}
