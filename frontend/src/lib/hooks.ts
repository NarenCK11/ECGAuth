import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

export interface Fetched<T> {
  data: T | null;
  /** true only until the first response arrives */
  loading: boolean;
  /** true while refetching; the previous data stays on screen */
  refetching: boolean;
  error: string | null;
  reload: () => void;
}

/** Fetch on mount and whenever `deps` change, keeping previous data visible while refetching. */
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[]): Fetched<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refetching, setRefetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    const mine = ++seq.current;
    setRefetching(true);
    setError(null);
    fn()
      .then((d) => { if (mine === seq.current) setData(d); })
      .catch((e) => { if (mine === seq.current) setError(e instanceof ApiError ? e.message : "Could not load data."); })
      .finally(() => { if (mine === seq.current) { setLoading(false); setRefetching(false); } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, refetching, error, reload };
}
