"use client";

import { useState } from "react";

import DataTable from "@/components/DataTable";
import { ErrorNote, Kpis, Panel, Pill } from "@/components/Panel";
import { api, type Row } from "@/lib/api";
import { useApi } from "@/lib/useApi";

type DataStatus = {
  assets: Row[];
  present: number;
  missing: number;
  ok: boolean;
};

type Check = { name: string; status: string; message: string };
type Validations = {
  reports: { source: string; checks: Check[]; failures: number; warnings: number }[];
  failing_checks: number;
  ok: boolean;
};

export default function HealthPage() {
  const status = useApi<DataStatus>("/api/data/status");
  const [validations, setValidations] = useState<Validations | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setValidations(null);
      setValidations(await api<Validations>("/api/data/validations"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="page-title">Data Health</h1>
      <p className="page-sub">
        Which data files the package expects on disk, and the full validation / drift suite (CSV vs SQLite vs parquet vs
        tracks.yaml).
      </p>

      <Kpis
        items={[
          { label: "Assets present", value: status.data?.present ?? "-" },
          { label: "Assets missing", value: status.data?.missing ?? "-" },
          { label: "Validation failures", value: validations ? validations.failing_checks : "-" },
        ]}
      />

      <Panel
        title="Data assets"
        right={
          <Pill status={status.data?.ok ? "ok" : "warn"}>
            {status.data?.ok ? "all present" : `${status.data?.missing} missing`}
          </Pill>
        }
      >
        {status.error ? <ErrorNote message={status.error} /> : null}
        {status.loading ? <p className="muted">Loading...</p> : (
          <DataTable rows={status.data?.assets ?? []} columns={["asset", "ok", "optional", "path", "role", "fix"]} />
        )}
      </Panel>

      <Panel title="Validation & drift suite" right={<button className="btn teal" disabled={busy} onClick={run}>{busy ? "Running..." : "Run validations"}</button>}>
        {error ? <ErrorNote message={error} /> : null}
        {validations ? (
          <>
            {validations.reports.map((r) => (
              <div key={r.source} className="mt12">
                <div className="row">
                  <span className="mono">{r.source}</span>
                  <Pill status={r.failures ? "fail" : r.warnings ? "warn" : "ok"}>
                    {r.failures ? `${r.failures} failures` : r.warnings ? `${r.warnings} warnings` : "all ok"}
                  </Pill>
                </div>
                <DataTable rows={r.checks} columns={["name", "status", "message"]} />
              </div>
            ))}
            <div className={`info-note ${validations.ok ? "" : "error-note"}`} style={{ marginTop: 12 }}>
              {validations.ok ? "All data checks passed." : `${validations.failing_checks} failing checks.`}
            </div>
          </>
        ) : (
          <p className="muted mt12 mb0">Run the suite to validate CSVs, SQLite, the training parquet and tracks.yaml.</p>
        )}
      </Panel>
    </>
  );
}
