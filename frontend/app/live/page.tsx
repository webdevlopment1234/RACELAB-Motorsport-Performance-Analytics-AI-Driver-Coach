"use client";

import { useCallback, useEffect, useState } from "react";

import DataTable, { type Row } from "@/components/DataTable";
import { ErrorNote, Panel, Pill } from "@/components/Panel";
import { api, type Snapshot } from "@/lib/api";

type Providers = { providers: string[]; active: string | null };
type Replays = { count: number; latest: string | null; replays: string[] };

export default function LivePage() {
  const [state, setState] = useState<Providers>({ providers: ["openf1", "mock", "replay"], active: null });
  const [preview, setPreview] = useState<Snapshot | null>(null);
  const [replays, setReplays] = useState<Replays>({ count: 0, latest: null, replays: [] });
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [prov, reps] = await Promise.all([
        api<Providers>("/api/live/providers"),
        api<Replays>("/api/live/replays"),
      ]);
      setState(prov);
      setReplays(reps);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function runPreview(provider: string) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      setPreview(await api<Snapshot>(`/api/live/preview?provider=${provider}`));
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function start(provider: string) {
    setBusy(true);
    setError(null);
    try {
      await api("/api/live/session", { method: "POST", body: JSON.stringify({ provider }) });
      setNote(`Session started with ${provider} - see the Race Intelligence page for the full dashboard.`);
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    try {
      await api("/api/live/session", { method: "DELETE" });
      await loadAll();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="page-title">LIVE</h1>
      <p className="page-sub">
        Live timing providers: <span className="mono">openf1</span> (free API, needs internet, 2023+ history),{" "}
        <span className="mono">mock</span> (offline demo), <span className="mono">replay</span> (saved snapshots).
      </p>

      <Panel
        title="Session"
        right={state.active ? <Pill status="info">{state.active}</Pill> : <Pill status="warn">idle</Pill>}
      >
        {error ? <ErrorNote message={error} /> : null}
        {note ? <div className="info-note">{note}</div> : null}
        <div className="row">
          {state.providers.map((p) => (
            <button key={p} className="btn" disabled={busy} onClick={() => start(p)}>
              Start {p}
            </button>
          ))}
          <button className="btn" disabled={busy} onClick={() => runPreview("mock")}>Preview mock</button>
          <button className="btn" disabled={busy} onClick={() => runPreview("openf1")}>Preview openf1</button>
          {state.active ? (
            <button className="btn" disabled={busy} onClick={stop}>End session</button>
          ) : null}
        </div>
      </Panel>

      <Panel title={`Saved replay snapshots (${replays.count})`}>
        {replays.count === 0 ? (
          <p className="muted">
            No snapshots yet. Start a session on the Race Intelligence page and press “Save snapshot as replay”.
          </p>
        ) : (
          <DataTable
            rows={replays.replays.map((path) => ({
              file: path.split(/[\\/]/).pop(),
              path,
              latest: path === replays.latest ? "yes" : "",
            }))}
          />
        )}
      </Panel>

      <div className="grid2">
        <Panel title="Preview snapshot data">
          {preview ? (
            <DataTable rows={preview.drivers ?? []} maxRows={24} />
          ) : (
            <p className="muted mt12 mb0">Use the preview buttons above.</p>
          )}
        </Panel>
        <Panel title="Preview telemetry flow">
          {preview ? (
            <DataTable rows={preview.latest_laps ?? []} maxRows={24} />
          ) : (
            <p className="muted mt12 mb0">Use the preview buttons above.</p>
          )}
        </Panel>
      </div>
    </>
  );
}
