"use client";

import { useState } from "react";

import DataTable, { type Row } from "@/components/DataTable";
import { ErrorNote, Panel } from "@/components/Panel";
import { useApi } from "@/lib/useApi";

type TableData = { count: number; columns: string[]; rows: Row[] };

export default function DriversPage() {
  const summary = useApi<TableData>("/api/drivers");
  const [selected, setSelected] = useState<number | null>(null);
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);

  const list = summary.data?.rows ?? [];
  const options: { driverId: number; name: string }[] = list.map((r) => ({
    driverId: Number(r.driverId),
    name: `${r.forename ?? ""} ${r.surname ?? ""}`.trim(),
  }));

  const sessionsHref = selected ? `/api/drivers/${selected}` : null;
  const h2hHref = a && b ? `/api/drivers/head-to-head?a=${a}&b=${b}` : null;

  const sessions = useApi<TableData>(sessionsHref);
  const h2h = useApi<TableData>(h2hHref);

  return (
    <>
      <h1 className="page-title">Drivers</h1>
      <p className="page-sub">Career summaries, session history and head-to-head comparisons.</p>

      <Panel title="Driver summary">
        {summary.error ? <ErrorNote message={summary.error} /> : null}
        {summary.loading ? <p className="muted">Loading...</p> : <DataTable rows={summary.data?.rows ?? []} maxRows={100} />}
      </Panel>

      <div className="grid2">
        <Panel title="Session history">
          <div className="row">
            <select
              value={selected ?? ""}
              onChange={(e) => setSelected(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Select driver...</option>
              {options.map((o) => (
                <option key={o.driverId} value={o.driverId}>
                  {o.name}
                </option>
              ))}
            </select>
          </div>
          {sessions.error ? <ErrorNote message={sessions.error} /> : null}
          {selected ? (sessions.loading ? <p className="muted">Loading...</p> : <DataTable rows={sessions.data?.rows ?? []} maxRows={40} />) : null}
        </Panel>

        <Panel title="Head-to-head">
          <div className="row">
            <select value={a ?? ""} onChange={(e) => setA(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Driver A...</option>
              {options.map((o) => (
                <option key={o.driverId} value={o.driverId}>{o.name}</option>
              ))}
            </select>
            <span className="mono muted">vs</span>
            <select value={b ?? ""} onChange={(e) => setB(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Driver B...</option>
              {options.map((o) => (
                <option key={o.driverId} value={o.driverId}>{o.name}</option>
              ))}
            </select>
          </div>
          {h2h.error ? <ErrorNote message={h2h.error} /> : null}
          {h2hHref ? (h2h.loading ? <p className="muted">Loading...</p> : <DataTable rows={h2h.data?.rows ?? []} />) : (
            <p className="muted mt12 mb0">Pick two drivers to compare.</p>
          )}
        </Panel>
      </div>
    </>
  );
}
