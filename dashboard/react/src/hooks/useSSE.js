import { useEffect, useRef, useState } from "react";
import { adaptSnapshot } from "../lib/payloadAdapter";

/**
 * useSSE — connects to the backend /api/stream SSE endpoint and
 * exposes the latest adapted snapshot.
 *
 * - Fetches /api/state once on mount for immediate display.
 * - Reconnects automatically after a 3-second delay on close.
 * - Skips keepalive comments ("...").
 * - Adapted shape: { obs, fc, risk, route, status, commState,
 *   connected, lastUpdate, ageHrs, updateSeq }
 */
export default function useSSE(url = "/api/stream") {
  const [data, setData] = useState(null);
  const [live, setLive] = useState(false);
  const retries = useRef(0);
  const ctrl = useRef(null);

  /* initial fetch from /api/state (JSON, not SSE) */
  useEffect(() => {
    let cancelled = false;
    fetch("/api/state", { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((snap) => {
        if (!cancelled && snap) setData(adaptSnapshot(snap));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  /* SSE subscription */
  useEffect(() => {
    let closed = false;

    function connect() {
      if (closed) return;
      const es = new EventSource(url);
      ctrl.current = es;

      es.onopen = () => { setLive(true); retries.current = 0; };

      es.onmessage = (evt) => {
        const raw = evt.data;
        if (!raw || raw.startsWith(":")) return;      // keepalive
        try {
          const snap = JSON.parse(raw);
          setData(adaptSnapshot(snap));
        } catch { /* malformed — skip */ }
      };

      es.onerror = () => {
        setLive(false);
        es.close();
        retries.current = Math.min(retries.current + 1, 10);
        const delay = 3000;
        if (!closed) setTimeout(connect, delay);
      };
    }

    connect();
    return () => { closed = true; ctrl.current?.close(); };
  }, [url]);

  return { data, live };
}
