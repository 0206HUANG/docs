"use client";
import { useEffect, useRef, useState } from "react";

/**
 * Poll an async fetcher on an interval and expose the latest data plus a
 * live-status indicator. Keeps showing the previous data while refetching so
 * the UI never flashes empty. Returns { data, loading, lastUpdated, refresh }.
 */
export function useLivePolling<T>(fetcher: () => Promise<T>, intervalMs = 10000) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  async function refresh() {
    try {
      const d = await fetcherRef.current();
      setData(d);
      setLastUpdated(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, intervalMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs]);

  return { data, loading, lastUpdated, refresh };
}

/** Small green pulsing "实时" badge shown next to page titles. */
export function LiveBadge({ lastUpdated }: { lastUpdated: Date | null }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-400">
      <span className="flex items-center gap-1 text-green-600">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        实时
      </span>
      {lastUpdated && <span>· {lastUpdated.toLocaleTimeString("zh-CN")}</span>}
    </span>
  );
}
