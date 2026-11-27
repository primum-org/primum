// What the board did, and why: its trace, followed while a screen shows it. The board keeps
// the last entries in memory and sends each new one as it is noted; this device keeps what
// it was sent, so that coming back to the screen asks only for what is new.

import { markRaw, reactive, watch, type WatchStopHandle } from "vue";

import { openTrace } from "@/api/client";
import type { TraceBody, TraceEntry } from "@/api/types";
import { RECONNECT_MAX_MS, RECONNECT_MIN_MS, session } from "@/session";

// As many as the board keeps (docs/specs/trace.md). So no mark of entries the board dropped
// before this device asked for them could ever be seen: a board that dropped some keeps
// as many entries newer than all this device has, and they take the place of all it has.
export const KEPT_ENTRIES = 1000;

export const trace = reactive({
  // Oldest first, as the board sends them. Replaced whole, never changed in place, and
  // not made deeply reactive: a thousand entries, each a proxy, cost every new one.
  entries: markRaw([]) as TraceEntry[],
  // The id of the trace they are of: another one means the board restarted.
  run: null as string | null,
});

let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;
let stopWatching: WatchStopHandle | null = null;

/** The number of the newest entry this device has; 0 for none. */
const lastHeld = (): number => trace.entries.at(-1)?.number ?? 0;

/** Take what the board sent; false when it must be asked again from the start. A body of
 * another trace (the board restarted) replaces what was held. Asked for what follows an
 * entry the new trace has already passed, the board sends only what follows it there: the
 * start of the new trace is missing, and it is asked for from 0 (docs/specs/trace.md). */
export function takeTrace(body: TraceBody): boolean {
  if (body.run !== trace.run) {
    trace.entries = markRaw([]);
    const whole = body.entries.length === 0 ? body.first > body.last : body.entries[0]?.number === body.first;
    // Not taken as the trace held: whatever comes next, of this run or another, is new.
    trace.run = whole ? body.run : null;
    if (!whole) return false;
  }
  const held = lastHeld();
  const fresh = body.entries.filter((entry) => entry.number > held);
  if (fresh.length > 0) trace.entries = markRaw([...trace.entries, ...fresh].slice(-KEPT_ENTRIES));
  return true;
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
      if (!takeTrace(body)) open(); // from 0, now that nothing is held
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

/** A line of the trace on screen: an entry, as deep as the chain of causes that led to it. */
export interface TraceLine {
  readonly entry: TraceEntry;
  readonly depth: number;
}

/** The entries as a person reads them: each chain that one entry started (an event, the
 * automations it concerned, what they did) together and in the order it happened, under
 * the entry that started it; the newest chain first. */
export function traceLines(entries: readonly TraceEntry[]): TraceLine[] {
  const held = new Set(entries.map((entry) => entry.number));
  const children = new Map<number, TraceEntry[]>();
  const roots: TraceEntry[] = [];
  for (const entry of entries) {
    // A cause that is not held (dropped, or of before this device asked) starts nothing here.
    if (entry.cause === null || !held.has(entry.cause)) roots.push(entry);
    else children.set(entry.cause, children.get(entry.cause) ?? []).get(entry.cause)?.push(entry);
  }
  const lines: TraceLine[] = [];
  const chain = (entry: TraceEntry, depth: number): void => {
    lines.push({ entry, depth });
    for (const child of children.get(entry.number) ?? []) chain(child, depth + 1);
  };
  for (const root of roots.reverse()) chain(root, 0);
  return lines;
}
