// Live run events over SSE. EventSource reconnects automatically and sends Last-Event-ID, so a dropped
// connection (or a page refresh that restores `known`) continues exactly after the last seen seq.
import { useEffect, useRef, useState } from "react";
import { EVENT_TYPES, type TraceEvent } from "@formal-lab/contracts";
import { API, get } from "./api";

export type StreamState = "connecting" | "live" | "reconnecting" | "ended" | "error";

export function useRunEvents(runId: string | undefined) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [state, setState] = useState<StreamState>("connecting");
  const lastSeq = useRef(0);

  useEffect(() => {
    if (!runId) return;
    let closed = false;
    let source: EventSource | null = null;
    lastSeq.current = 0;
    setEvents([]);
    setState("connecting");
    // 1) load what exists (fast, paged REST) 2) follow live updates from the last seq over SSE
    (async () => {
      let after = 0;
      const all: TraceEvent[] = [];
      for (;;) {
        const page = await get<TraceEvent[]>(`/runs/${runId}/events?after_seq=${after}&limit=2000`);
        all.push(...page);
        if (page.length < 2000) break;
        after = page[page.length - 1].seq;
      }
      if (closed) return;
      lastSeq.current = all.length ? all[all.length - 1].seq : 0;
      setEvents(all);
      source = new EventSource(`${API}/runs/${runId}/events/stream?after_seq=${lastSeq.current}`);
      source.onopen = () => setState("live");
      source.onerror = () => setState((s) => (s === "ended" ? s : "reconnecting"));
      source.addEventListener("end", () => { setState("ended"); source?.close(); });
      const onEvent = (msg: MessageEvent) => {
        const ev = JSON.parse(msg.data) as TraceEvent;
        if (ev.seq <= lastSeq.current) return; // de-duplicate across reconnects
        lastSeq.current = ev.seq;
        setEvents((xs) => [...xs, ev]);
      };
      source.onmessage = onEvent;
      // every event type of the contract (generated list): named SSE events are only delivered to listeners
      for (const t of EVENT_TYPES) source.addEventListener(t, onEvent as EventListener);
    })().catch(() => setState("error"));
    return () => { closed = true; source?.close(); };
  }, [runId]);

  return { events, state };
}
