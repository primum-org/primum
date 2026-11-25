import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import OutputRow from "@/components/OutputRow.vue";
import { session } from "@/session";
import { board, output, state } from "@/testing/board";

const DIMMER = { id: "dim", name: "Dimmer", actions: ["on", "off", "set"] };
const row = (of = output()) => {
  const asked = board(state({ outputs: [of] }));
  return { asked, view: mount(OutputRow, { props: { output: of } }) };
};
const button = (view: ReturnType<typeof mount>, label: string) =>
  view.findAll("button").find((each) => each.text() === label);

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("the switch asks for the other state and says the one the board reports", async () => {
  const { asked, view } = row(output({ on: true }));

  expect(view.get(".switch").attributes("aria-pressed")).toBe("true");
  expect(view.get(".switch-state").text()).toBe("On");
  await view.get(".switch").trigger("click");

  expect(asked).toEqual([
    { method: "PUT", path: "/api/outputs/led", body: { action: "off", arguments: {}, durationMs: null } },
  ]);
});

test("offline the switch says nothing, is neither on nor off, and takes nothing", () => {
  const { view } = row(output({ on: true }));
  session.online = false;

  return view.vm.$nextTick().then(() => {
    expect(view.get(".switch").attributes("aria-pressed")).toBe("mixed");
    expect(view.get(".switch-state").text()).toBe("");
    expect(view.get(".switch").attributes("disabled")).toBeDefined();
    expect(button(view, "Test")?.attributes("disabled")).toBeDefined();
  });
});

test("in panic nothing can be asked of an output", () => {
  const of = output();
  board(state({ outputs: [of], panic: true }));
  const view = mount(OutputRow, { props: { output: of } });

  expect(view.get(".switch").attributes("disabled")).toBeDefined();
  expect(button(view, "Test")?.attributes("disabled")).toBeDefined();
});

test("a test turns the output on for ten seconds", async () => {
  const { asked, view } = row();

  await button(view, "Test")?.trigger("click");

  expect(asked[0]?.body).toEqual({ action: "on", arguments: {}, durationMs: 10000 });
});

test("an output left on on purpose cannot be tested: the test would turn it off", () => {
  const { view } = row(output({ on: true }));

  expect(button(view, "Test")?.attributes("disabled")).toBeDefined();
});

test("a test under way counts down on this device's clock, never past zero", async () => {
  const { view } = row(output({ on: true, remainingMs: 4200, controlledBy: "test" }));

  expect(view.get('[role="timer"]').text()).toBe("Test: off in 5 s");
  await vi.advanceTimersByTimeAsync(3000);
  expect(view.get('[role="timer"]').text()).toBe("Test: off in 2 s");
  await vi.advanceTimersByTimeAsync(5000);
  expect(view.get('[role="timer"]').text()).toBe("Test: off in 0 s");
});

test("an output that could not be confirmed off says so instead of counting down", () => {
  const { view } = row(output({ remainingMs: 0, restFailed: true }));

  expect(view.find('[role="timer"]').exists()).toBe(false);
  expect(view.text()).toContain("could not be confirmed that it is off");
});

test("only an output that takes a level has a slider", () => {
  expect(row().view.find(".level-slider").exists()).toBe(false);
  expect(row(output(DIMMER)).view.find(".level-slider").exists()).toBe(true);
});

test("moving the slider shows the number, and the level is asked for once, on letting go", async () => {
  const { asked, view } = row(output({ ...DIMMER, level: 20 }));
  const slider = view.get(".level-slider");

  await slider.trigger("pointerdown");
  await slider.setValue("35");
  await slider.setValue("60");
  expect(view.get(".level-value").text()).toBe("60 %");
  expect(asked).toEqual([]);
  await slider.trigger("pointerup");
  await slider.trigger("change"); // a browser sends it after letting go
  await flushPromises();

  expect(asked.map((each) => each.body)).toEqual([{ action: "set", arguments: { level: 60 }, durationMs: null }]);
});

test("keys pressed one after another add up, each asked for as it is let go", async () => {
  // The board is slow: none of its answers comes before the last key.
  const pending: (() => void)[] = [];
  const of = output({ ...DIMMER, level: 20 });
  const asked = board(state({ outputs: [of] }));
  vi.stubGlobal("fetch", (_url: URL, init: RequestInit) => {
    asked.push({ method: "PUT", path: "", body: JSON.parse(String(init.body)) });
    return new Promise<Response>((resolve) => pending.push(() => resolve(new Response(JSON.stringify(session.state)))));
  });
  const view = mount(OutputRow, { props: { output: of } });
  const slider = view.get(".level-slider");

  for (const level of ["21", "22", "23"]) {
    await slider.trigger("keydown");
    await slider.setValue(level);
    await slider.trigger("keyup");
    await slider.trigger("change");
    await flushPromises();
  }

  // The state after the first key arrives while the others are still unanswered.
  await view.setProps({ output: output({ ...DIMMER, level: 21 }) });

  expect((slider.element as HTMLInputElement).value).toBe("23");
  expect(asked.map((each) => (each.body as { arguments: { level: number } }).arguments.level)).toEqual([21, 22, 23]);

  // Once the last is answered, the slider is the board's again.
  session.state = state({ outputs: [output({ ...DIMMER, level: 23 })] });
  await view.setProps({ output: output({ ...DIMMER, level: 23 }) });
  pending.forEach((answer) => answer());
  await flushPromises();
  await view.setProps({ output: output({ ...DIMMER, level: 50 }) });

  expect((slider.element as HTMLInputElement).value).toBe("50");
});

test("a slider that is held is the person's: a state that arrives does not move it", async () => {
  const { view } = row(output({ ...DIMMER, level: 20 }));
  const slider = view.get(".level-slider");

  await slider.trigger("pointerdown");
  await slider.setValue("60");
  await view.setProps({ output: output({ ...DIMMER, level: 80 }) });

  expect((slider.element as HTMLInputElement).value).toBe("60");
});

test("let go where it was, a slider asks for nothing", async () => {
  const { asked, view } = row(output({ ...DIMMER, level: 20 }));
  const slider = view.get(".level-slider");

  await slider.trigger("pointerdown");
  await slider.setValue("50");
  await slider.setValue("20");
  await slider.trigger("pointerup");

  expect(asked).toEqual([]);
});

test("during a test a new level keeps the time the test had left", async () => {
  const { asked, view } = row(output({ ...DIMMER, on: true, level: 100, remainingMs: 6000, controlledBy: "test" }));
  const slider = view.get(".level-slider");

  await vi.advanceTimersByTimeAsync(2000);
  await slider.trigger("pointerdown");
  await slider.setValue("40");
  await slider.trigger("pointerup");

  expect(asked[0]?.body).toEqual({ action: "set", arguments: { level: 40 }, durationMs: 4000 });
});

test("a level set at once, with nothing held, is asked for", async () => {
  const { asked, view } = row(output({ ...DIMMER, level: 20 }));

  await view.get(".level-slider").setValue("70"); // assistive technology: input, then change
  await view.get(".level-slider").trigger("change");

  expect(asked.map((each) => each.body)).toEqual([{ action: "set", arguments: { level: 70 }, durationMs: null }]);
});

test("a slider taken from the hand by panic lets go without asking", async () => {
  const of = output({ ...DIMMER, level: 20 });
  const { asked, view } = row(of);
  const slider = view.get(".level-slider");

  await slider.trigger("pointerdown");
  await slider.setValue("60");
  session.state = state({ outputs: [of], panic: true });
  await view.vm.$nextTick();
  await slider.trigger("pointerup");

  expect(asked).toEqual([]);
  expect((slider.element as HTMLInputElement).value).toBe("20");
});

test("an output held by hand says so and can be given back to the sequences", async () => {
  const { asked, view } = row(output({ on: true, controlledBy: "manual" }));

  expect(view.text()).toContain("Held by hand");
  await button(view, "Release")?.trigger("click");

  expect(asked).toEqual([{ method: "DELETE", path: "/api/outputs/led", body: undefined }]);
});

test("an output a sequence commands says so, and has nothing to release", () => {
  const { view } = row(output({ on: true, controlledBy: "sequence" }));

  expect(view.text()).toContain("A sequence is commanding it.");
  expect(button(view, "Release")).toBeUndefined();
});
