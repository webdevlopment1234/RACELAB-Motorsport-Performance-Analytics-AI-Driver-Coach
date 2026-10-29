"use client";

import { useState, type FormEvent } from "react";

import { ErrorNote, Findings, Panel } from "@/components/Panel";
import { api, type CoachReport, type Row } from "@/lib/api";
import { useApi } from "@/lib/useApi";

type TableData = { count: number; columns: string[]; rows: Row[] };

export default function CoachPage() {
  const [raceId, setRaceId] = useState<string>("");
  const [driverId, setDriverId] = useState<string>("");
  const [raceReport, setRaceReport] = useState<CoachReport | null>(null);
  const [lapReport, setLapReport] = useState<CoachReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const drivers = useApi<TableData>("/api/drivers");

  const driverOptions: Row[] = (drivers.data?.rows ?? []).slice(0, 400).map((d) => ({
    id: Number(d.driverId),
    name: `${d.forename ?? ""} ${d.surname ?? ""}`.trim(),
  }));

  async function runRaceCoach(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      setRaceReport(null);
      setRaceReport(await api<CoachReport>(`/api/coach/race?race_id=${raceId}&driver_id=${driverId}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function runLapCoach(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      setLapReport(null);
      setLapReport(await api<CoachReport>(`/api/coach/laps?driver_id=${driverId}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <h1 className="page-title">AI Driver Coach</h1>
      <p className="page-sub">
        Evidence-based, numerical coaching: race-scoped pace gaps, sector consistency and tyre context. Never coaches on
        incomplete or low-confidence data.
      </p>

      {error ? <ErrorNote message={error} /> : null}

      <div className="grid2">
        <Panel title="Post-race coach">
          <form onSubmit={runRaceCoach}>
            <div className="row">
              <input
                type="text"
                placeholder="raceId (from analytics calendar)"
                value={raceId}
                onChange={(e) => setRaceId(e.target.value)}
              />
              <input
                type="text"
                placeholder="driverId (from drivers page)"
                value={driverId}
                onChange={(e) => setDriverId(e.target.value)}
              />
              <button className="btn primary" type="submit" disabled={!raceId || !driverId}>
                Analyze race
              </button>
            </div>
          </form>
          {raceReport ? (
            <div className="mt12">
              <span className="mono muted">
                {raceReport.driver} | {raceReport.n_laps} laps
              </span>
              <Findings findings={raceReport.findings} warnings={raceReport.warnings} />
            </div>
          ) : null}
        </Panel>

        <Panel title="Laps coach (2018+, all seasons)">
          <form onSubmit={runLapCoach}>
            <div className="row">
              <select value={driverId} onChange={(e) => setDriverId(e.target.value)}>
                <option value="">Driver...</option>
                {driverOptions.map((d) => (
                  <option key={String(d.id)} value={String(d.id)}>{String(d.name)}</option>
                ))}
              </select>
              <button className="btn primary" type="submit" disabled={!driverId}>
                Analyze laps
              </button>
            </div>
          </form>
          {lapReport ? (
            <div className="mt12">
              <span className="mono muted">
                {lapReport.driver} | {lapReport.n_laps} laps
              </span>
              <Findings findings={lapReport.findings} warnings={lapReport.warnings} />
            </div>
          ) : null}
        </Panel>
      </div>
    </>
  );
}
