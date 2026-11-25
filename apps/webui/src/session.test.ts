import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { listen, mustPair, pair, RECONNECT_MIN_MS, session, stop, unpair } from "@/session";

// A WebSocket the test drives: what was opened, and the board's side of each one.
class FakeSocket extends EventTarget {
  static opened: FakeSocket[] = [];

  constructor(readonly url: URL) {
    super();
    FakeSocket.opened.push(this);
  }

  send(state: unknown): void {
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(state) }));
  }

  close(): void {
    this.dispatchEvent(new Event("close"));
  }
}

const STATE = { panic: false, outputs: [] };
const PAIRED = { required: true, device: { id: "1", name: "phone", current: true } };
const UNPAIRED = { required: true, device: null };
const last = (): FakeSocket => FakeSocket.opened.at(-1) as FakeSocket;
const answers = (body: unknown, status = 200) => async () => new Response(JSON.stringify(body), { status });

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.opened = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  session.pairing = PAIRED;
  session.state = null;
});

afterEach(() => {
  stop();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("the state is the last one the board sent, and the board is online once it has", () => {
  listen();
  expect(session.online).toBe(false);

  last().send(STATE);
  last().send({ ...STATE, panic: true });

  expect(session.online).toBe(true);
  expect(session.state).toMatchObject({ panic: true });
  expect(String(last().url)).toMatch(/^ws:.*\/api\/ws$/);
});

test("a lost connection is said at once and tried again by itself", async () => {
  vi.stubGlobal("fetch", answers(PAIRED));
  listen();
  last().send(STATE);

  last().close();
  expect(session.online).toBe(false);
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);

  expect(FakeSocket.opened).toHaveLength(2);
});

test("a board that does not come back is asked less and less often", async () => {
  vi.stubGlobal("fetch", answers(PAIRED));
  listen();

  last().close(); // never opened
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);
  last().close();
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);

  expect(FakeSocket.opened).toHaveLength(2); // the third waits twice as long
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);
  expect(FakeSocket.opened).toHaveLength(3);
});

test("a device the board forgot stops trying and must pair again", async () => {
  vi.stubGlobal("fetch", answers(UNPAIRED));
  listen();
  last().send(STATE);

  last().close();
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS * 20);

  expect(mustPair()).toBe(true);
  expect(FakeSocket.opened).toHaveLength(1);
});

test("pairing starts listening, and unpairing stops for good", async () => {
  session.pairing = UNPAIRED;
  vi.stubGlobal("fetch", answers({ token: "t", device: PAIRED.device }));
  await pair("123456", "phone");
  expect(mustPair()).toBe(false);
  expect(FakeSocket.opened).toHaveLength(1);

  vi.stubGlobal("fetch", answers(UNPAIRED));
  await unpair();
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS * 20);

  expect(mustPair()).toBe(true);
  expect(FakeSocket.opened).toHaveLength(1);
});

test("a service that asks for no pairing needs none", () => {
  session.pairing = { required: false, device: null };

  expect(mustPair()).toBe(false);
});
