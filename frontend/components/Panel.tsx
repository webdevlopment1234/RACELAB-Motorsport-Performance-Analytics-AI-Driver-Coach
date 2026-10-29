"use client";

import React from "react";

export function Panel({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <span>{title}</span>
        {right ? <span>{right}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function Pill({ status, children }: { status: "ok" | "warn" | "fail" | "info"; children: React.ReactNode }) {
  return <span className={`pill ${status}`}>{children}</span>;
}

export function Kpis({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  return (
    <div className="kpis">
      {items.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="num">{k.value}</div>
          <div className="label">{k.label}</div>
        </div>
      ))}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="error-note">{message}</div>;
}

export function WarnNote({ message }: { message: string }) {
  return <div className="warn-note">{message}</div>;
}

export function Findings({ findings, warnings }: { findings: { area: string; text: string; confidence: number; conditions?: string }[]; warnings: string[] }) {
  return (
    <div>
      {warnings.length > 0 && <div className="warn-note">{warnings.join("; ")}</div>}
      {findings.length === 0 && warnings.length === 0 ? (
        <p className="muted mt12 mb0">No findings yet.</p>
      ) : null}
      {findings.map((f, i) => (
        <div className="finding" key={i}>
          <span className="area">{f.area}</span>
          {f.text}
          <span className="conf">confidence {Math.round(f.confidence * 100)}%</span>
          {f.conditions ? <span className="conf"> | {f.conditions}</span> : null}
        </div>
      ))}
    </div>
  );
}
