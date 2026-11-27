import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { TraceEntry } from "@/api/types";
import { board, state } from "@/testing/board";
import { trace } from "@/trace";
import ActivityView from "@/views/ActivityView.vue";

class FakeSocket extends EventTarget {
  static opened: FakeSocket[] = [];

  constructor(readonly url: URL) {
    super();
    FakeSocket.opened.push(this);
  }

  close(): void {}
}

const entry = (number: number, over: Partial<TraceEntry> = {}): TraceEntry => ({
  number,
  atMs: 125_000,
  time: null,
  kind: "event.happened",
  params: { id: "e", name: "Presence", source: "element" },
  cause: null,
  ...over,
});

beforeEach(() => {
  FakeSocket.opened = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  Object.assign(trace, { entries: [], run: null, gaps: [] });
});

afterEach(() => vi.unstubAllGlobals());

test("automations, schedules and the trace, in that order; the trace is followed while shown", () => {
  board(
    state({
      automations: [{ id: "a", name: "Welcome", enabled: true, problem: null }],
      schedules: [{ id: "s", name: "Opening hours", open: true }],
    }),
  );

  const view = mount(ActivityView);

  expect(view.findAll("h2").map((heading) => heading.text())).toEqual(["Automations", "Schedules", "What the board did"]);
  expect(FakeSocket.opened).toHaveLength(1);
  expect(view.text()).toContain("Asking the board for what it did");
});

test("an automation that failed comes first, and says why", () => {
  const problem = { code: "automation.action_failed", params: { automation: "Night", action: 2 } };
  board(
    state({
      automations: [
        { id: "a", name: "Welcome", enabled: true, problem: null },
        { id: "b", name: "Night", enabled: false, problem },
      ],
    }),
  );

  const rows = mount(ActivityView).findAll("section:first-of-type li");

  expect(rows[0]?.text()).toContain("Night");
  expect(rows[0]?.text()).toContain("Off");
  expect(rows[0]?.text()).toContain("An action of the automation Night failed");
  expect(rows[1]?.text()).toContain("Welcome");
  expect(rows[1]?.text()).toContain("On");
});

test("a schedule says whether its window is open, or that the time is not known", () => {
  board(
    state({
      schedules: [
        { id: "1", name: "Morning", open: true },
        { id: "2", name: "Night", open: false },
        { id: "3", name: "Weekend", open: null },
      ],
    }),
  );

  const text = mount(ActivityView).text();

  expect(text).toContain("Open now");
  expect(text).toContain("Closed");
  expect(text).toContain("Time unknown");
});

test("the trace shows each chain under what started it, and when", () => {
  board(state());
  Object.assign(trace, {
    run: "r1",
    entries: [
      entry(1),
      entry(2, { kind: "automation.acted", params: { id: "a", name: "Welcome" }, cause: 1, time: "2026-11-27T09:30:05+00:00" }),
    ],
  });

  const lines = mount(ActivityView).findAll(".trace-entry");

  expect(lines.map((line) => line.attributes("data-number"))).toEqual(["1", "2"]);
  expect(lines[0]?.text()).toContain("Presence happened.");
  expect(lines[0]?.text()).toContain("2 min 5 s after the board started");
  expect(lines[1]?.classes()).toContain("depth-1");
  expect(lines[1]?.find("time").text()).not.toBe("");
});

test("missing entries are marked, and a trace with nothing says so", () => {
  board(state());
  Object.assign(trace, { run: "r1", entries: [entry(1), entry(5)], gaps: [5] });
  expect(mount(ActivityView).find(".trace-gap").text()).toContain("Some entries are missing here");

  Object.assign(trace, { run: "r1", entries: [], gaps: [] });
  expect(mount(ActivityView).text()).toContain("Nothing yet.");
});

test("what went wrong has the warning icon", () => {
  board(state());
  Object.assign(trace, {
    run: "r1",
    entries: [entry(1, { kind: "output.failed", params: { id: "o", name: "LED" } }), entry(2)],
  });

  const lines = mount(ActivityView).findAll(".trace-entry");

  expect(lines.find((line) => line.attributes("data-number") === "1")?.find(".icon").exists()).toBe(true);
  expect(lines.find((line) => line.attributes("data-number") === "2")?.find(".icon").exists()).toBe(false);
});
