"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import DataTable, { type Row } from "@/components/DataTable";
import { ErrorNote, Panel } from "@/components/Panel";
import { useApi } from "@/lib/useApi";

type TableData = { count: number; columns: string[]; rows: Row[] };

export default function CircuitsPage() {
  const table = useApi<TableData>("/api/circuits");
  const [circuit, setCircuit] = useState<string | null>(null);

  const refs: { ref: string; name: string }[] = useMemo(() => {
    const rows = table.data?.rows ?? [];
    return rows.map((r) => ({ ref: String(r.circuitRef), name: String(r.name) }));
  }, [table.data]);

  const winners = useApi<TableData>(circuit ? `/api/circuits/${circuit}/winners` : null);
  const pace = useApi<TableData>(circuit ? `/api/circuits/pace?circuit=${circuit}` : null);

  const paceData = useMemo(() => {
    const rows = pace.data?.rows ?? [];
    return rows
      .map((r) => ({
        year: String(r["year"] ?? r["raceId"] ?? ""),
        fastest: Number(r["fastest_sec"] ?? r["time_sec"] ?? r["best_sec"] ?? 0),
      }))
      .filter((d) => d.fastest > 0);
  }, [pace.data]);

  return (
    <>
      <h1 className="page-title">Circuits</h1>
      <p className="page-sub">Track characteristics, historical winners and pace evolution.</p>

      <Panel title="Circuits">
        <div className="row mt12">
          <select value={circuit ?? ""} onChange={(e) => setCircuit(e.target.value || null)}>
            <option value="">All circuits...</option>
            {refs.map((r) => (
              <option key={r.ref} value={r.ref}>{r.name}</option>
            ))}
          </select>
          {circuit ? <span className="muted mono">{circuit}</span> : null}
        </div>
        {table.error ? <ErrorNote message={table.error} /> : null}
        {table.loading ? <p className="muted">Loading...</p> : <DataTable rows={table.data?.rows ?? []} maxRows={80} />}
      </Panel>

      {circuit ? (
        <>
          <Panel title={`Historical winners - ${circuit}`}>
            {winners.error ? <ErrorNote message={winners.error} /> : null}
            {winners.loading ? <p className="muted">Loading...</p> : <DataTable rows={winners.data?.rows ?? []} maxRows={40} />}
          </Panel>

          <Panel title="Pace evolution">
            {pace.error ? <ErrorNote message={pace.error} /> : null}
            {paceData.length > 0 ? (
              <div style={{ width: "100%", height: 300 }}>
                <ResponsiveContainer>
                  <LineChart data={paceData}>
                    <CartesianGrid stroke="#1d242e" />
                    <XAxis dataKey="year" stroke="#8b98a9" />
                    <YAxis stroke="#8b98a9" domain={["auto", "auto"]} />
                    <Tooltip
                      contentStyle={{ background: "#11161d", border: "1px solid #1d242e", borderRadius: 8 }}
                      labelStyle={{ color: "#e6edf3" }}
                    />
                    <Line type="monotone" dataKey="fastest" stroke="#00e5c0" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="muted">No pace data (fastf1_laps required in f1.db).</p>
            )}
          </Panel>
        </>
      ) : null}
    </>
  );
}
