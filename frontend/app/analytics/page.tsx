"use client";

import { useState } from "react";

import DataTable from "@/components/DataTable";
import { ErrorNote, Kpis, Panel } from "@/components/Panel";
import { useApi } from "@/lib/useApi";

type TableData = { count: number; columns: string[]; rows: Record<string, unknown>[] };

const TABS = ["Calendar", "Standings", "Drivers", "Constructors", "Circuits"] as const;
type Tab = (typeof TABS)[number];

function StandingsTab() {
  const [year, setYear] = useState(2023);
  const { data, error, loading } = useApi<TableData>(`/api/standings?year=${year}`);
  return (
    <>
      <div className="row mt12">
        <label className="muted">Season</label>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {[1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020, 2021, 2022, 2023, 2024].map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>
      {error ? <ErrorNote message={error} /> : null}
      {loading ? <p className="muted">Loading...</p> : <DataTable rows={data?.rows ?? []} maxRows={40} />}
    </>
  );
}

export default function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>("Calendar");

  const calendar = useApi<TableData>("/api/calendar");
  const drivers = useApi<TableData>("/api/drivers");
  const constructors = useApi<TableData>("/api/constructors");
  const circuits = useApi<TableData>("/api/circuits");

  const counts = {
    races: calendar.data?.count ?? 0,
    drivers: drivers.data?.count ?? 0,
    constructors: constructors.data?.count ?? 0,
    circuits: circuits.data?.count ?? 0,
  };

  const tabData =
    tab === "Calendar" ? calendar
      : tab === "Standings" ? null
        : tab === "Drivers" ? drivers
          : tab === "Constructors" ? constructors
            : circuits;

  return (
    <>
      <h1 className="page-title">Analytics</h1>
      <p className="page-sub">Historical F1 dataset: 1950+, fully offline against the bundled SQLite database.</p>

      <Kpis
        items={[
          { label: "Races", value: counts.races },
          { label: "Drivers", value: counts.drivers },
          { label: "Constructors", value: counts.constructors },
          { label: "Circuits", value: counts.circuits },
        ]}
      />

      <Panel title="Tables">
        <div className="tabs">
          {TABS.map((t) => (
            <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>
        {tab === "Standings" ? <StandingsTab /> : (
          <>
            {tabData?.error ? <ErrorNote message={tabData.error} /> : null}
            {tabData?.loading ? <p className="muted">Loading...</p> : <DataTable rows={tabData?.data?.rows ?? []} maxRows={100} />}
          </>
        )}
      </Panel>
    </>
  );
}
