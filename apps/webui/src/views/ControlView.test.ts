import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, expect, test, vi } from "vitest";

import AlertStrip from "@/components/AlertStrip.vue";
import { session } from "@/session";
import { board, json, output, state } from "@/testing/board";
import ControlView from "@/views/ControlView.vue";

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
  const after = state({ outputs: [output({ on: true, controlledBy: "manual" })] });
  board(state({ outputs: [output()] }), () => json(after));
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

test("a device the board no longer knows is sent to pair again", async () => {
  const answers = [json({ code: "pairing.required", params: {} }, 401), json({ required: true, device: null })];
  board(state({ outputs: [output()] }), () => answers.shift() ?? json(null, 500));
  const view = mount(ControlView);

  await view.get(".switch").trigger("click");
  await flushPromises();

  expect(session.pairing).toEqual({ required: true, device: null });
  expect(session.refused).toBeNull();
});
