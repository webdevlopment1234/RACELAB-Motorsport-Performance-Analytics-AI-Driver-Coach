export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5000";

export type TableData = {
  count: number;
  columns: string[];
  rows: Record<string, unknown>[];
};

export type Finding = {
  area: string;
  text: string;
  confidence: number;
  conditions?: string;
};

export type CoachReport = {
  driver: string;
  n_laps: number;
  findings: Finding[];
  warnings: string[];
  markdown?: string;
};

export type Row = Record<string, unknown>;

export type Snapshot = {
  source: string;
  fetched_at: string;
  session: Record<string, unknown>;
  is_live: boolean;
  is_empty: boolean;
  warnings: string[];
  drivers: Row[];
  leaderboard: Row[];
  latest_laps: Row[];
  weather: Row[];
  race_control: Row[];
  stints: Row[];
  intervals: Row[];
  telemetry: Row[];
};

export type ModelInfo = {
  ok: boolean;
  path?: string;
  error?: string;
  input_columns?: string[];
  data_version?: string;
  split?: string;
  seed?: number;
};

export type ModelsStatus = {
  ok: boolean;
  data?: Record<string, unknown>;
  models?: Record<string, ModelInfo>;
};

export type ApiErrorShape = { error?: string; detail?: string; status?: number };
export type ApiResult<T> = T;

export class FetchError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = body as ApiErrorShape;
    throw new FetchError((err?.error ?? `HTTP ${res.status}`) + (err?.detail ? `\n${err.detail}` : ""), res.status);
  }
  return body as T;
}

export function table<T = Row>(path: string, init?: RequestInit): Promise<T> {
  return api<T>(path, init);
}
