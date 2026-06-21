import { useEffect, useRef, useState } from "react";

// Poll an async function on an interval, exposing data/error/loading.
export function usePoll<T>(fn: () => Promise<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const savedFn = useRef(fn);
  savedFn.current = fn;

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const result = await savedFn.current();
        if (active) {
          setData(result);
          setError(null);
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [intervalMs]);

  return { data, error };
}

export function formatTime(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return "--:--";
  const s = Math.floor(seconds % 60);
  const m = Math.floor((seconds / 60) % 60);
  const h = Math.floor(seconds / 3600);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}
