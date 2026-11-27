import { type DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import { afterEach, expect, test, vi } from "vitest";

import VariableRow from "@/components/VariableRow.vue";
import { session } from "@/session";
import { board, json, state, variable } from "@/testing/board";

const row = (of = variable(), answer?: () => Response) => {
  const asked = board(state({ variables: [of] }), answer);
  return { asked, view: mount(VariableRow, { props: { variable: of } }) };
};
const sent = (asked: ReturnType<typeof board>) => asked.map((each) => each.body);
// Keys pressed in a field, without leaving it: the test utils' setValue leaves it too.
async function type(field: Pick<DOMWrapper<Element>, "element" | "trigger">, text: string): Promise<void> {
  (field.element as HTMLInputElement).value = text;
  await field.trigger("input");
}

afterEach(() => vi.unstubAllGlobals());

test("a number with both limits is a slider, asked for on letting go, by the variable's id", async () => {
  const { asked, view } = row();
  const slider = view.get(".level-slider");

  expect(slider.attributes()).toMatchObject({ min: "0", max: "100", step: "1" });
  await slider.trigger("pointerdown");
  await slider.setValue("35");
  expect(asked).toEqual([]);
  await slider.trigger("pointerup");

  expect(asked).toEqual([{ method: "PUT", path: "/api/variables/v1", body: { value: 35 } }]);
});

test("a number with decimals moves in round steps, so that round values are on the slider", () => {
  const step = (min: number, max: number) =>
    row(variable({ type: "number", value: min, min, max })).view.get(".level-slider").attributes("step");

  expect(step(0, 2)).toBe("0.02");
  expect(step(15, 30)).toBe("0.2"); // a hundredth, 0.15, would miss 20 and 21
  expect(step(0, 60)).toBe("1"); // and 0.6 would miss 1, 2 and 5
  expect(step(0, 100)).toBe("1");
});

test("a whole number with more values than a slider can hold is typed, within its limits", async () => {
  const { asked, view } = row(variable({ name: "delay_ms", value: 500, min: 0, max: 10000 }));
  const field = view.get("input");

  expect(view.find(".level-slider").exists()).toBe(false);
  expect(field.attributes()).toMatchObject({ type: "number", min: "0", max: "10000", step: "1" });
  await type(field, "1234");
  await field.trigger("change");

  expect(sent(asked)).toEqual([{ value: 1234 }]);
});

test("a number without both limits is typed, and sent when the field is left or Enter pressed", async () => {
  const { asked, view } = row(variable({ name: "visits", value: 12, min: 0, max: null }));
  const field = view.get("input");

  expect(field.attributes()).toMatchObject({ type: "number", min: "0" });
  await type(field, "40");
  expect(asked).toEqual([]);
  await field.trigger("change");

  expect(sent(asked)).toEqual([{ value: 40 }]);
});

test("an integer is never sent with decimals, nor a field left empty, and why is said", async () => {
  const { asked, view } = row(variable({ value: 12, min: null, max: null }));
  const field = view.get("input");

  await type(field, "3.7");
  await field.trigger("change");
  await type(field, "");
  await field.trigger("change");
  await flushPromises();

  expect(asked).toEqual([]);
  expect((field.element as HTMLInputElement).value).toBe("12"); // back to what the board has
  expect(session.refused).toEqual({ code: "variable.value_invalid", params: { name: "brightness", type: "integer" } });
});

test("true or false is a switch", async () => {
  const { asked, view } = row(variable({ name: "open", type: "boolean", value: false, min: null, max: null }));

  expect(view.get(".switch").attributes("aria-pressed")).toBe("false");
  await view.get(".switch").trigger("click");

  expect(sent(asked)).toEqual([{ value: true }]);
});

test("a text is typed and sent when the field is left", async () => {
  const { asked, view } = row(variable({ name: "greeting", type: "text", value: "Hello", min: null, max: null }));
  const field = view.get("input");

  expect(field.attributes("type")).toBe("text");
  await type(field, "Welcome");
  await field.trigger("change");

  expect(sent(asked)).toEqual([{ value: "Welcome" }]);
});

test("a value the board refuses goes back to the one it has, and the refusal is said", async () => {
  const refusal = { code: "variable.value_out_of_range", params: { name: "visits", value: 900, min: 0, max: 500 } };
  const { view } = row(variable({ name: "visits", value: 12, min: 0, max: null }), () => json(refusal, 422));
  const field = view.get("input");

  await type(field, "900");
  await field.trigger("change");
  await flushPromises();

  expect((field.element as HTMLInputElement).value).toBe("12");
  expect(session.refused).toMatchObject({ code: "variable.value_out_of_range" });
});

test("a value that arrives from the board replaces what is shown, unless the person is typing", async () => {
  const { view } = row(variable({ name: "visits", value: 12, min: 0, max: null }));
  const field = view.get("input");

  await view.setProps({ variable: variable({ name: "visits", value: 13, min: 0, max: null }) });
  expect((field.element as HTMLInputElement).value).toBe("13");
  await field.trigger("focus");
  await type(field, "4");
  await view.setProps({ variable: variable({ name: "visits", value: 14, min: 0, max: null }) });

  expect((field.element as HTMLInputElement).value).toBe("4");
});

test("offline, and in a way that says nothing stale, nothing can be changed", async () => {
  const { view } = row(variable({ type: "boolean", value: true, min: null, max: null }));
  session.online = false;
  await view.vm.$nextTick();

  expect(view.get(".switch").attributes()).toMatchObject({ "aria-pressed": "mixed", disabled: "" });
});

test("a variable is changed in panic too: it moves nothing by itself", () => {
  const of = variable({ type: "boolean", value: true, min: null, max: null });
  board(state({ variables: [of], panic: true }));

  expect(mount(VariableRow, { props: { variable: of } }).get(".switch").attributes("disabled")).toBeUndefined();
});

test("a variable kept across restarts says so", () => {
  expect(row(variable({ persistent: true })).view.text()).toContain("Kept");
  expect(row(variable({ persistent: false })).view.text()).not.toContain("Kept");
});
