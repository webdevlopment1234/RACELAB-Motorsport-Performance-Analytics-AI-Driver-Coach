"use client";

import React from "react";

export type Row = Record<string, unknown>;

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "-";
  if (typeof v === "number") {
    const r = Math.round(v * 1000) / 1000;
    return String(r);
  }
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

export default function DataTable({
  columns,
  rows,
  maxRows,
  compact,
}: {
  columns?: string[];
  rows?: Row[];
  maxRows?: number;
  compact?: boolean;
}) {
  if (!rows || rows.length === 0) {
    return <p className="muted mt12 mb0">No data.</p>;
  }
  const cols = columns && columns.length
    ? columns
    : [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const shown = maxRows ? rows.slice(0, maxRows) : rows;
  return (
    <div className="scroll-x">
      <table className="data">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{compact ? c : c.replace(/_/g, " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{fmt(r[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {maxRows && rows.length > maxRows ? (
        <p className="muted">Showing {shown.length} of {rows.length} rows</p>
      ) : null}
    </div>
  );
}
