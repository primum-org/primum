import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { TraceBody, TraceEntry } from "@/api/types";
import { RECONNECT_MIN_MS, session } from "@/session";
import { followTrace, KEPT_ENTRIES, takeTrace, trace, traceLines, unfollowTrace } from "@/trace";

// A WebSocket the test drives: what was opened, and the board's side of each one.
class FakeSocket extends EventTarget {
  static opened: FakeSocket[] = [];
  closed = false;

  constructor(readonly url: URL) {
    super();
    FakeSocket.opened.push(this);
  }

  send(body: TraceBody): void {
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(body) }));
  }

  close(): void {
    this.closed = true;
    this.dispatchEvent(new Event("close"));
  }
}

const entry = (number: number, over: Partial<TraceEntry> = {}): TraceEntry => ({
  number,
  atMs: number * 1000,
  time: null,
  kind: "event.happened",
  params: { id: "e", name: "Presence", source: "element" },
  cause: null,
  ...over,
});
const body = (entries: TraceEntry[], run = "r1"): TraceBody => ({
  entries,
  first: entries[0]?.number ?? 1,
  last: entries.at(-1)?.number ?? 0,
  run,
});
const numbers = (): number[] => trace.entries.map((each) => each.number);
const last = (): FakeSocket => FakeSocket.opened.at(-1) as FakeSocket;

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.opened = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  Object.assign(trace, { entries: [], run: null });
  session.online = true;
});

afterEach(() => {
  unfollowTrace();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("what the board sends is added after what is held, and nothing twice", () => {
  takeTrace(body([entry(1), entry(2)]));
  takeTrace(body([entry(2), entry(3)]));

  expect(numbers()).toEqual([1, 2, 3]);
});

test("a trace of another run (the board restarted) replaces what was held", () => {
  takeTrace(body([entry(1), entry(2), entry(3)]));
  expect(takeTrace(body([entry(1)], "r2"))).toBe(true); // whole: from its first entry

  expect(numbers()).toEqual([1]);
  expect(trace.run).toBe("r2");
});

test("a board that restarted and went further than this device had is asked again from the start", async () => {
  // 21 entries held; the board restarts out of sight and notes 35: asked for what follows
  // 21, it sends 22 to 35 of the new trace, whose start this device must not miss.
  takeTrace(body(Array.from({ length: 21 }, (_, index) => entry(index + 1))));
  followTrace();
  expect(last().url.searchParams.get("after")).toBe("21");

  last().send({ ...body(Array.from({ length: 14 }, (_, index) => entry(index + 22)), "r2"), first: 1 });
  await vi.advanceTimersByTimeAsync(0);

  expect(FakeSocket.opened).toHaveLength(2);
  expect(last().url.searchParams.get("after")).toBe("0");
  last().send(body(Array.from({ length: 35 }, (_, index) => entry(index + 1)), "r2"));
  expect(numbers()).toEqual(Array.from({ length: 35 }, (_, index) => index + 1));
});

test("no more entries are kept than the board keeps", () => {
  takeTrace(body([entry(1)]));
  takeTrace(body(Array.from({ length: KEPT_ENTRIES }, (_, index) => entry(index + 4))));

  expect(trace.entries).toHaveLength(KEPT_ENTRIES);
  expect(trace.entries[0]?.number).toBe(4);
});

test("the trace is followed from the last entry held, and only while the board is there", async () => {
  takeTrace(body([entry(1), entry(2)]));
  followTrace();
  expect(last().url.searchParams.get("after")).toBe("2");
  expect(last().url.pathname).toMatch(/\/api\/trace\/ws$/);

  session.online = false; // silent: taken for gone
  await vi.advanceTimersByTimeAsync(0);
  expect(last().closed).toBe(true);
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS * 20);
  expect(FakeSocket.opened).toHaveLength(1); // not looked for while gone

  last().closed = false;
  session.online = true;
  await vi.advanceTimersByTimeAsync(0);
  expect(FakeSocket.opened).toHaveLength(2);
});

test("a connection that closes is opened again, from what is held by then", async () => {
  followTrace();
  last().send(body([entry(1), entry(2), entry(3)]));
  last().dispatchEvent(new Event("close")); // the board's side

  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);

  expect(FakeSocket.opened).toHaveLength(2);
  expect(last().url.searchParams.get("after")).toBe("3");
});

test("leaving the screen stops following, and keeps what was sent", async () => {
  followTrace();
  last().send(body([entry(1)]));

  unfollowTrace();
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS * 20);

  expect(last().closed).toBe(true);
  expect(FakeSocket.opened).toHaveLength(1);
  expect(numbers()).toEqual([1]);
});

test("each chain is under the entry that started it, in the order it happened, the newest chain first", () => {
  const entries = [
    entry(1, { kind: "service.started", params: {} }),
    entry(2), // an event
    entry(3, { kind: "automation.acted", params: { id: "a", name: "Welcome" }, cause: 2 }),
    entry(4, { kind: "automation.did_not_act", params: { id: "b", name: "Night" }, cause: 2 }),
    entry(5, { kind: "sequence.started", params: { id: "s", name: "Show", by: "automation" }, cause: 3 }),
    entry(6, { kind: "sequence.ended", params: { id: "s", name: "Show" } }),
  ];

  const lines = traceLines(entries).map((line) => [line.entry.number, line.depth]);

  expect(lines).toEqual([[6, 0], [2, 0], [3, 1], [5, 2], [4, 1], [1, 0]]);
});

test("an entry whose cause is no longer held starts a chain of its own", () => {
  const lines = traceLines([entry(7, { cause: 3 })]);

  expect(lines).toEqual([{ entry: entry(7, { cause: 3 }), depth: 0 }]);
});
