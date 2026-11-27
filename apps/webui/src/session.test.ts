import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { COMMAND_TIMEOUT_MS } from "@/api/client";
import { connect, listen, mustPair, pair, RECONNECT_MIN_MS, session, SILENCE_MS, stop, unpair } from "@/session";

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
  session.problem = null;
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

test("a board that answers with an error is asked again, and the error is said", async () => {
  const broken = { code: "pairing.unreadable", params: {} };
  vi.stubGlobal("fetch", answers(broken, 500));
  listen();
  last().send(STATE);

  last().close();
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);
  expect(session.problem).toMatchObject({ code: "pairing.unreadable" });
  expect(FakeSocket.opened).toHaveLength(1); // nothing to listen to yet

  vi.stubGlobal("fetch", answers(PAIRED));
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS * 4); // the wait after the second failure

  expect(FakeSocket.opened).toHaveLength(2);
  expect(session.problem).toBeNull();
});

test("a board that is broken when the app starts is asked again until it answers", async () => {
  session.pairing = null;
  vi.stubGlobal("fetch", answers({ code: "pairing.unreadable", params: {} }, 500));

  await connect(); // must not raise: the app is mounted after it
  expect(FakeSocket.opened).toHaveLength(0);

  vi.stubGlobal("fetch", answers(PAIRED));
  await vi.advanceTimersByTimeAsync(RECONNECT_MIN_MS);

  expect(FakeSocket.opened).toHaveLength(1);
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

// A fetch that never answers, and gives up when the request is taken back.
const silent = (_url: URL, init: RequestInit) =>
  new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });

test("a board that does not answer a question is out of reach, not an order left undone", async () => {
  session.pairing = null;
  vi.stubGlobal("fetch", silent);

  const asked = connect();
  await vi.advanceTimersByTimeAsync(COMMAND_TIMEOUT_MS);
  await asked;

  expect(session.problem).toBe("offline");
  expect(session.refused).toBeNull();
});

test("a board out of reach for long is still being asked, and said so", async () => {
  vi.stubGlobal("fetch", silent);
  listen();
  last().send(STATE);
  last().close();

  await vi.advanceTimersByTimeAsync(COMMAND_TIMEOUT_MS * 6);

  expect(session.problem).toBe("offline");
  expect(session.online).toBe(false);
});

test("a board that goes silent without closing anything is taken for gone, and looked for again", async () => {
  // Frozen, or out of the Wi-Fi's reach: the connection stays open and says nothing. A
  // board that is there says its state again every two seconds.
  vi.stubGlobal("fetch", answers(PAIRED));
  listen();
  last().send(STATE);
  await vi.advanceTimersByTimeAsync(SILENCE_MS - 1);
  expect(session.online).toBe(true);

  await vi.advanceTimersByTimeAsync(1);

  expect(session.online).toBe(false);
  expect(session.settled).toBe(true);
  expect(FakeSocket.opened).toHaveLength(2);
});

test("a board that goes on saying its state is never taken for gone", async () => {
  listen();
  for (let beats = 0; beats < 10; beats++) {
    last().send(STATE);
    await vi.advanceTimersByTimeAsync(SILENCE_MS - 1);
  }

  expect(session.online).toBe(true);
  expect(FakeSocket.opened).toHaveLength(1);
});

test("a connection that opens and never says anything is given up too", async () => {
  vi.stubGlobal("fetch", answers(PAIRED));
  listen();

  await vi.advanceTimersByTimeAsync(SILENCE_MS);

  expect(session.settled).toBe(true);
  expect(FakeSocket.opened).toHaveLength(2);
});
