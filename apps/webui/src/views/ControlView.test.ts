import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, expect, test, vi } from "vitest";

import AlertStrip from "@/components/AlertStrip.vue";
import { COMMAND_TIMEOUT_MS } from "@/api/client";
import { listen, session, stop } from "@/session";
import { board, json, output, state } from "@/testing/board";
import ControlView from "@/views/ControlView.vue";

class FakeSocket extends EventTarget {
  static last: FakeSocket | null = null;

  constructor() {
    super();
    FakeSocket.last = this;
  }

  close(): void {}
}

const SEQUENCE = { id: "show", name: "Show", running: false };
const INPUT = { id: "pir", name: "Presence", active: true, lostEvents: 0 };

afterEach(() => vi.unstubAllGlobals());

test("the screen lists what the board runs, and only the kinds there are", () => {
  board(state({ outputs: [output()], sequences: [SEQUENCE] }));

  const view = mount(ControlView);

  expect(view.findAll("h2").map((heading) => heading.text())).toEqual(["Outputs", "Sequences"]);
  expect(view.text()).not.toContain("Nothing to control");
});

test("a board that runs nothing says so", () => {
  board(state());

  expect(mount(ControlView).text()).toContain("Nothing to control");
});

test("the panic button is never disabled, and asks the board at once", async () => {
  const asked = board(state({ outputs: [output()], panic: true }));
  const view = mount(ControlView);
  session.online = false;
  await view.vm.$nextTick();

  expect(view.get(".panic").attributes("disabled")).toBeUndefined();
  await view.get(".panic").trigger("click");

  expect(asked).toEqual([{ method: "POST", path: "/api/panic", body: undefined }]);
});

test("a sequence is started and stopped by its id, and stopping needs it running", async () => {
  const asked = board(state({ sequences: [SEQUENCE] }));
  const view = mount(ControlView);
  const [start, stop] = view.findAll(".row button");

  expect(stop?.attributes("disabled")).toBeDefined();
  await start?.trigger("click");

  expect(asked).toEqual([{ method: "POST", path: "/api/sequences/show/start", body: undefined }]);
});

test("an input says what it reads, and nothing when the board is gone", async () => {
  board(state({ inputs: [INPUT] }));
  const view = mount(ControlView);

  expect(view.get(".row-state").text()).toBe("Active");
  session.online = false;
  await view.vm.$nextTick();

  expect(view.get(".row-state").text()).toBe("");
});

test("the state the board answers a command with is the one shown", async () => {
  const before = state({ outputs: [output()] });
  const after = state({ outputs: [output({ on: true, controlledBy: "manual" })] });
  board(before, () => json(after));
  const view = mount(ControlView);

  await view.get(".switch").trigger("click");
  await flushPromises();

  expect(view.get(".switch").attributes("aria-pressed")).toBe("true");
});

test("what the board refuses is said in words, until it is closed", async () => {
  board(state({ outputs: [output()] }), () => json({ code: "panic.active", params: {} }, 409));
  const view = mount(ControlView);
  const alerts = mount(AlertStrip);

  await view.get(".switch").trigger("click");
  await flushPromises();
  expect(alerts.get('[role="alert"]').text()).toContain("Panic is active");
  await alerts.findAll("button").find((each) => each.text() === "Close")?.trigger("click");

  expect(alerts.find('[role="alert"]').exists()).toBe(false);
});

test("panic is said on every screen, and released from there", async () => {
  const asked = board(state({ panic: true }));
  const alerts = mount(AlertStrip);

  expect(alerts.get('[role="alert"]').text()).toContain("Panic is active");
  await alerts.findAll("button").find((each) => each.text() === "Release panic")?.trigger("click");

  expect(asked).toEqual([{ method: "DELETE", path: "/api/panic", body: undefined }]);
});

test("the board's alerts are said in words, with the names they are about", () => {
  const outputs = [output({ name: "Relay", restFailed: true }), output({ id: "m", name: "Motor", restFailed: true })];
  board(state({ outputs, variablesUnsaved: true }));

  const text = mount(AlertStrip).text();

  expect(text).toContain("Could not confirm that these are off: Relay and Motor.");
  expect(text).toContain("could not save the values");
});

test("a device the board no longer knows is told its order was not carried out", async () => {
  const answers = [json({ code: "pairing.required", params: {} }, 401), json({ required: true, device: null })];
  board(state({ outputs: [output()] }), () => answers.shift() ?? json(null, 500));
  const view = mount(ControlView);

  await view.get(".switch").trigger("click");
  await flushPromises();

  expect(session.pairing).toEqual({ required: true, device: null });
  expect(session.refused).toBe("forgotten");
});

test("an order the board never got is said as not sent, once, and not as being tried again", async () => {
  board(state({ outputs: [output()] }), () => {
    throw new TypeError("Failed to fetch");
  });
  const view = mount(ControlView);
  const alerts = mount(AlertStrip);

  await view.get(".panic").trigger("click");
  await flushPromises();

  expect(session.refused).toBe("unsent");
  expect(alerts.text()).toContain("was not sent");
  expect(alerts.text()).not.toContain("Retrying");
});

test("an order that was not sent is forgotten when the board is back", async () => {
  board(state({ outputs: [output()] }));
  session.refused = "unsent";
  vi.stubGlobal("WebSocket", FakeSocket);

  listen();
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(state()) }));

  expect(session.refused).toBeNull();
  stop();
});

test("what the board itself refused stays when the connection comes back", () => {
  board(state({ outputs: [output()] }));
  session.refused = { code: "panic.active", params: {} };
  vi.stubGlobal("WebSocket", FakeSocket);

  listen();
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(state()) }));

  expect(session.refused).toEqual({ code: "panic.active", params: {} });
  stop();
});

test("panic never says every output is off while one could not be confirmed off", () => {
  board(state({ panic: true, outputs: [output({ name: "Dimmer", restFailed: true })] }));

  const text = mount(AlertStrip).text();

  expect(text).not.toContain("every output is off");
  expect(text).toContain("Panic is active");
  expect(text).toContain("Could not confirm that these are off: Dimmer.");
});

test("panic with every output at rest says so", () => {
  board(state({ panic: true, outputs: [output()] }));

  expect(mount(AlertStrip).text()).toContain("every output is off");
});

test("while the first connection is being made, nothing says it was lost", async () => {
  board(state());
  Object.assign(session, { online: false, state: null, settled: false });
  const alerts = mount(AlertStrip);

  expect(alerts.find('[role="status"]').exists()).toBe(false);
  session.settled = true; // it could not be made, or it was made and lost
  await alerts.vm.$nextTick();

  expect(alerts.get('[role="status"]').text()).toContain("No connection with the board");
});

test("an answer that comes late never replaces a state that is later than it", async () => {
  // The switch is asked for; before its answer comes, another device presses panic and
  // the WebSocket says so. The answer, of before the panic, must not bring the switch back.
  const before = state({ outputs: [output()] });
  const answer = state({ outputs: [output({ on: true, controlledBy: "manual" })] });
  const panicked = state({ outputs: [output()], panic: true });
  let release = (): void => {};
  board(before);
  vi.stubGlobal("fetch", (url: URL) => {
    // Only the switch is held back: whatever else is asked is answered at once.
    if (!url.pathname.includes("/outputs/")) return Promise.resolve(json(null, 500));
    return new Promise<Response>((resolve) => {
      release = function release() {
        resolve(json(answer));
      };
    });
  });
  vi.stubGlobal("WebSocket", FakeSocket);
  listen();
  const view = mount(ControlView);
  const alerts = mount(AlertStrip);
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(before) }));
  await flushPromises();

  await view.get(".switch").trigger("click");
  expect(release.name).toBe("release"); // the switch was asked for, and its answer is held
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(panicked) }));
  release();
  await new Promise((resolve) => setTimeout(resolve, 20)); // the answer is read and taken, or not
  await flushPromises();

  expect(alerts.text()).toContain("Panic is active");
  expect(view.get(".switch").attributes("aria-pressed")).toBe("false");
  stop();
});

test("a board that was restarted starts its numbers over, and is believed", () => {
  board(state({ outputs: [output({ on: true })] }));
  vi.stubGlobal("WebSocket", FakeSocket);

  listen(); // a new connection
  FakeSocket.last?.dispatchEvent(
    new MessageEvent("message", { data: JSON.stringify({ ...state({ outputs: [] }), revision: 1 }) }),
  );

  expect(session.state?.outputs).toEqual([]);
  stop();
});

test("an order the board does not answer in time is said as that, and the connection is made again", async () => {
  vi.useFakeTimers();
  board(state({ outputs: [output()] }));
  const paired = { required: true, device: { id: "1", name: "phone", current: true } };
  vi.stubGlobal("fetch", (url: URL, init: RequestInit) => {
    // The board takes the order and says nothing; asked anything else, it answers.
    if (!url.pathname.endsWith("/panic")) return Promise.resolve(json(paired));
    return new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    });
  });
  vi.stubGlobal("WebSocket", FakeSocket);
  listen();
  const before = FakeSocket.last;
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(state()) }));
  const view = mount(ControlView);
  const alerts = mount(AlertStrip);

  await view.get(".panic").trigger("click");
  await vi.advanceTimersByTimeAsync(COMMAND_TIMEOUT_MS - 1);
  expect(session.refused).toBeNull();
  await vi.advanceTimersByTimeAsync(1);
  await flushPromises();

  expect(session.refused).toBe("unanswered");
  expect(alerts.text()).toContain("did not answer");
  expect(session.online).toBe(false); // a board that does not answer is not taken for connected
  expect(FakeSocket.last === before).toBe(false);
  stop();
  vi.useRealTimers();
});

test("the alert of a package that does not run goes when the board runs one again", async () => {
  const problem = { code: "package.invalid", params: {} };
  const broken = { running: null, active: null, previous: null, staged: null, problem, fixed: false };
  const answers = [json(broken), json({ ...broken, problem: null })];
  board(state(), () => answers.shift() ?? json(null, 500));
  vi.stubGlobal("WebSocket", FakeSocket);
  listen();
  const alerts = mount(AlertStrip);
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(state()) }));
  await flushPromises();
  expect(alerts.text()).toContain("The active package is not running");

  // Another device activates a package that runs: the board says its new state.
  FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(state({ outputs: [output()] })) }));
  await flushPromises();

  expect(alerts.text()).not.toContain("The active package is not running");
  stop();
});

test("an order the board answers while the screen is reconnecting shows at once that the board is there", async () => {
  // The service came back and the screen is still waiting to try again: panic is pressed,
  // the board does it and answers. The screen must not go on saying there is no connection.
  const paired = { required: true, device: { id: "1", name: "phone", current: true } };
  board(state({ outputs: [output()] }));
  const panicked = state({ outputs: [output()], panic: true });
  vi.stubGlobal("fetch", (url: URL) => Promise.resolve(json(url.pathname.endsWith("/panic") ? panicked : paired)));
  vi.stubGlobal("WebSocket", FakeSocket);
  Object.assign(session, { online: false, settled: true });
  FakeSocket.last = null;
  const view = mount(ControlView);

  await view.get(".panic").trigger("click");
  await flushPromises();

  expect(session.state?.panic).toBe(true);
  expect(FakeSocket.last).not.toBeNull(); // connecting again now, not when the wait is over
  stop();
});
