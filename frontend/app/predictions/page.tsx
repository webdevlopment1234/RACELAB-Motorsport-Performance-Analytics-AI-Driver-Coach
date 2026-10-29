"use client";

import { useEffect, useState, type FormEvent } from "react";

import DataTable from "@/components/DataTable";
import { ErrorNote, Panel, Pill } from "@/components/Panel";
import { api, type ModelInfo, type ModelsStatus, type Row } from "@/lib/api";
import { usePoll } from "@/lib/useApi";

type TrainStatus = { status: string; error: string | null; tasks: Record<string, unknown> };
type Prediction = { task: string; input_columns: string[]; prediction: Row[] };

const TASKS = ["finish", "is_dnf", "is_podium", "is_winner"] as const;

function DefaultValue({ column }: { column: string }) {
  const n = /_?(year|id|rate|count)s?$/.test(column);
  return n ? 10 : 1.0;
}

export default function PredictionsPage() {
  const status = usePoll<ModelsStatus>("/api/models/status", 10000);
  const train = usePoll<TrainStatus>("/api/models/train/status", 2000);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState<(typeof TASKS)[number]>("finish");
  const [values, setValues] = useState<Record<string, string>>({});
  const [pred, setPred] = useState<Prediction | null>(null);

  const columns = (status.data?.models?.[task]?.input_columns ?? []) as string[];

  useEffect(() => {
    setValues(Object.fromEntries(columns.map((c) => [c, String(DefaultValue({ column: c }))])));
  }, [task, columns.join("|")]);

  async function runTrain() {
    setError(null);
    try {
      await api("/api/models/train", { method: "POST" });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function predict() {
    setBusy(true);
    setError(null);
    setPred(null);
    try {
      const row = Object.fromEntries(columns.map((c) => [c, values[c]]));
      setPred(await api<Prediction>("/api/predict", {
        method: "POST",
        body: JSON.stringify({ task, row }),
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await predict();
  }

  const training = train.data?.status === "running";
  const model = status.data?.models?.[task];

  return (
    <>
      <h1 className="page-title">Predictions</h1>
      <p className="page-sub">Post-qualifying race models: finish order, DNF, podium and win probability.</p>

      <Panel
        title="Model artifacts"
        right={
          <div className="row">
            <Pill status={status.data?.ok ? "ok" : "warn"}>{status.data?.ok ? "ready" : "not ready"}</Pill>
            <button className="btn" disabled={training} onClick={runTrain}>
              {training ? "Training..." : "Train all"}
            </button>
          </div>
        }
      >
        {status.error ? <ErrorNote message={status.error} /> : null}
        {train.data?.status === "error" ? <ErrorNote message={`training failed: ${train.data.error}`} /> : null}
        {status.loading ? <p className="muted">Loading...</p> : (
          <div>
            {TASKS.map((t) => {
              const info: ModelInfo | undefined = status.data?.models?.[t];
              return (
                <div className="row mt12" key={t}>
                  <span className="mono" style={{ width: 110 }}>{t}</span>
                  {info?.ok ? (
                    <>
                      <Pill status="ok">validated</Pill>
                      <span className="muted mono">
                        inputs={info.input_columns?.length} | {info.split} | seed={info.seed} | {info.data_version}
                      </span>
                    </>
                  ) : (
                    <>
                      <Pill status="fail">{info?.error ? "missing" : "unknown"}</Pill>
                      <span className="muted">{info?.error ?? "checking..."}</span>
                    </>
                  )}
                </div>
              );
            })}
            {training ? <div className="info-note">Training artifacts in the background - progress updates live.</div> : null}
          </div>
        )}
      </Panel>

      <Panel title="Scoring form">
        <div className="row">
          {TASKS.map((t) => (
            <button key={t} className={`btn ${task === t ? "teal" : ""}`} onClick={() => setTask(t)}>
              {t}
            </button>
          ))}
        </div>
        {model && !model.ok ? (
          <div className="warn-note mt12">
            The {task} artifact is not trained yet. Press “Train all” or run `f1-analytics train`.
          </div>
        ) : null}
        {columns.length > 0 ? (
          <form onSubmit={handleSubmit}>
            <div className="grid2 mt12">
              {columns.map((c) => (
                <div key={c}>
                  <label className="muted mono" style={{ fontSize: 11 }}>{c}</label>
                  <input
                    type="text"
                    value={values[c] ?? ""}
                    onChange={(e) => setValues((v) => ({ ...v, [c]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
            <button className="btn primary" disabled={busy || !model?.ok} type="submit">
              Predict
            </button>
          </form>
        ) : (
          <p className="muted mt12">Select a task with a trained artifact to see its input form.</p>
        )}
        {pred ? (
          <div className="mt12">
            <h3 className="mt0 mono">Result</h3>
            <DataTable rows={pred.prediction} />
          </div>
        ) : null}
      </Panel>
    </>
  );
}
