"use client";

import { useCallback, useEffect, useState } from "react";

type State<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
};

export function useApi<T>(path: string | null, deps: unknown[] = []): State<T> & { reload: () => void } {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: !!path });
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!path) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetch(path)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!alive) return;
        if (!r.ok) throw new Error((body?.error as string) ?? `HTTP ${r.status}`);
        setState({ data: body as T, error: null, loading: false });
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);

  return { ...state, reload };
}

export function usePoll<T>(path: string | null, intervalMs = 5000): State<T> & { reload: () => void } {
  const state = useApi<T>(path);
  const { reload } = state;

  useEffect(() => {
    if (!path) return;
    const id = setInterval(reload, intervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, intervalMs]);

  return state;
}
