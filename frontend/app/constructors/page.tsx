"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import DataTable, { type Row } from "@/components/DataTable";
import { ErrorNote, Panel } from "@/components/Panel";
import { useApi } from "@/lib/useApi";

type TableData = { count: number; columns: string[]; rows: Row[] };

const YEARS = [2020, 2021, 2022, 2023, 2024];

export default function ConstructorsPage() {
  const summary = useApi<TableData>("/api/constructors");
  const pitStops = useApi<TableData>("/api/constructors/pit-stops");
  const [year, setYear] = useState(2023);
  const season = useApi<TableData>(`/api/constructors/${year}/points`);

  const chartData = useMemo(() => {
    const rows = season.data?.rows ?? [];
    return rows
      .map((r) => ({
        name: String(r["constructor"] ?? r["name"] ?? "?"),
        points: Number(r["points"] ?? 0),
      }))
      .sort((x, y) => y.points - x.points);
  }, [season.data]);

  return (
    <>
      <h1 className="page-title">Constructors</h1>
      <p className="page-sub">Team summaries, seasonal points battle and pit-stop stats.</p>

      <Panel title={`Season points - ${year}`}>
        <div className="row mb0">
          <label className="muted">Season</label>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <span className="muted">Points from the bundled dataset (CSV fallback covers 1950-2024).</span>
        </div>
        {season.error ? <ErrorNote message={season.error} /> : null}
        {chartData.length > 0 ? (
          <div style={{ width: "100%", height: 380 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} layout="vertical" margin={{ left: 40, right: 20 }}>
                <CartesianGrid stroke="#1d242e" />
                <XAxis type="number" stroke="#8b98a9" />
                <YAxis type="category" dataKey="name" width={120} stroke="#8b98a9" />
                <Tooltip
                  contentStyle={{ background: "#11161d", border: "1px solid #1d242e", borderRadius: 8 }}
                  labelStyle={{ color: "#e6edf3" }}
                />
                <Bar dataKey="points" fill="#e10600" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="muted">No points data for {year}.</p>
        )}
      </Panel>

      <Panel title="Constructor summary">
        {summary.error ? <ErrorNote message={summary.error} /> : null}
        {summary.loading ? <p className="muted">Loading...</p> : <DataTable rows={summary.data?.rows ?? []} maxRows={60} />}
      </Panel>

      <Panel title="Pit-stop stats">
        {pitStops.error ? <ErrorNote message={pitStops.error} /> : null}
        {pitStops.loading ? <p className="muted">Loading...</p> : <DataTable rows={pitStops.data?.rows ?? []} maxRows={40} />}
      </Panel>
    </>
  );
}
