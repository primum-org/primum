// What the board did, and why: its trace, followed while a screen shows it. The board keeps
// the last entries in memory and sends each new one as it is noted; this device keeps what
// it was sent, so that coming back to the screen asks only for what is new.

import { reactive, watch, type WatchStopHandle } from "vue";

import { openTrace } from "@/api/client";
import type { TraceBody, TraceEntry } from "@/api/types";
import { RECONNECT_MAX_MS, RECONNECT_MIN_MS, session } from "@/session";

// As many as the board keeps (docs/specs/trace.md): more would be of nothing it still has.
export const KEPT_ENTRIES = 1000;

export const trace = reactive({
  // Oldest first, as the board sends them.
  entries: [] as TraceEntry[],
  // The id of the trace they are of: another one means the board restarted.
  run: null as string | null,
  // Entries before which some were noted and dropped by the board before this device
  // asked for them: the screen says that something is missing there.
  gaps: [] as number[],
});

let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;
let stopWatching: WatchStopHandle | null = null;

/** The number of the newest entry this device has; 0 for none. */
const lastHeld = (): number => trace.entries.at(-1)?.number ?? 0;

/** Take what the board sent. A body of another trace (the board restarted) replaces what
 * was held; one that starts past the entry after the last held says some were missed. */
export function takeTrace(body: TraceBody): void {
  if (body.run !== trace.run) {
    trace.entries = [];
    trace.gaps = [];
    trace.run = body.run;
  }
  const held = lastHeld();
  const fresh = body.entries.filter((entry) => entry.number > held);
  const first = fresh[0];
  if (held > 0 && first !== undefined && first.number > held + 1) trace.gaps.push(first.number);
  if (fresh.length === 0) return;
  const entries = [...trace.entries, ...fresh];
  trace.entries = entries.slice(-KEPT_ENTRIES);
  const oldest = trace.entries[0]?.number ?? 0;
  trace.gaps = trace.gaps.filter((number) => number > oldest);
}

/** Follow the trace for as long as a screen shows it: from what is new since the last
 * entry held, and again whenever the board is back after it was out of reach. */
export function followTrace(): void {
  stopWatching?.();
  // The trace says nothing while the board does nothing: whether the board is there is the
  // state's to tell, by its beat. Gone, the trace is let go; back, it is asked for again.
  stopWatching = watch(
    () => session.online,
    (online) => (online ? open() : close()),
    { immediate: true },
  );
}

/** Stop following the trace. What was sent stays, for the next time it is followed. */
export function unfollowTrace(): void {
  stopWatching?.();
  stopWatching = null;
  close();
}

function open(delay = RECONNECT_MIN_MS): void {
  close();
  let opened = false;
  const current = openTrace(
    lastHeld(),
    (body) => {
      opened = true;
      takeTrace(body);
    },
    () => {
      if (socket !== current) return; // closed on purpose, or replaced
      socket = null;
      // A connection that worked starts the waits over; one that never did lengthens them.
      const next = opened ? RECONNECT_MIN_MS : Math.min(delay * 2, RECONNECT_MAX_MS);
      retry = setTimeout(() => open(next), opened ? RECONNECT_MIN_MS : delay);
    },
  );
  socket = current;
}

function close(): void {
  if (retry !== null) clearTimeout(retry);
  retry = null;
  const closing = socket;
  socket = null;
  closing?.close();
}

/** A line of the trace on screen: an entry, as deep as the chain of causes that led to it,
 * or a mark where entries are missing. */
export type TraceLine =
  | { readonly kind: "entry"; readonly entry: TraceEntry; readonly depth: number }
  | { readonly kind: "gap"; readonly before: number };

/** The entries as a person reads them: each chain that one entry started (an event, the
 * automations it concerned, what they did) together and in the order it happened, under
 * the entry that started it; the newest chain first. The marks of missing entries go
 * between the chains they fall between. */
export function traceLines(entries: readonly TraceEntry[], gaps: readonly number[]): TraceLine[] {
  const held = new Set(entries.map((entry) => entry.number));
  const children = new Map<number, TraceEntry[]>();
  const roots: TraceEntry[] = [];
  for (const entry of entries) {
    // A cause that is not held (dropped, or of before this device asked) starts nothing here.
    if (entry.cause === null || !held.has(entry.cause)) roots.push(entry);
    else children.set(entry.cause, [...(children.get(entry.cause) ?? []), entry]);
  }
  const lines: TraceLine[] = [];
  const chain = (entry: TraceEntry, depth: number): void => {
    lines.push({ kind: "entry", entry, depth });
    for (const child of children.get(entry.number) ?? []) chain(child, depth + 1);
  };
  const newestFirst = roots.reverse();
  newestFirst.forEach((root, index) => {
    chain(root, 0);
    const below = newestFirst[index + 1]?.number ?? 0;
    for (const gap of gaps) if (gap <= root.number && gap > below) lines.push({ kind: "gap", before: gap });
  });
  return lines;
}
