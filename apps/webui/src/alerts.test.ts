import { expect, test } from "vitest";

import { alertsOf } from "@/alerts";
import { output, state } from "@/testing/board";

const schedule = { id: "s", name: "Evenings", open: null };

test("a board with nothing wrong has no alerts", () => {
  expect(alertsOf(state({ outputs: [output()] }), null)).toEqual([]);
});

test("outputs that could not be confirmed off are named together", () => {
  const outputs = [output({ name: "Relay", restFailed: true }), output({ id: "b", name: "Lamp" }), output({ id: "c", name: "Motor", restFailed: true })];

  expect(alertsOf(state({ outputs }), null)).toEqual([{ kind: "rest_failed", names: ["Relay", "Motor"] }]);
});

test("inputs that lost changes are named", () => {
  const inputs = [{ id: "a", name: "Button", active: false, lostEvents: 2 }, { id: "b", name: "Door", active: true, lostEvents: 0 }];

  expect(alertsOf(state({ inputs }), null)).toEqual([{ kind: "lost_events", names: ["Button"] }]);
});

test("values that could not be saved are an alert", () => {
  expect(alertsOf(state({ variablesUnsaved: true }), null)).toEqual([{ kind: "variables_unsaved" }]);
});

test("not knowing the time matters only when a schedule waits for it", () => {
  expect(alertsOf(state({ timeKnown: false }), null)).toEqual([]);
  expect(alertsOf(state({ timeKnown: false, schedules: [schedule] }), null)).toEqual([{ kind: "time_unknown" }]);
});

test("an active package that does not run comes first, with why", () => {
  const problem = { code: "hal.pin_in_use", params: { pin: 17 } };
  const packages = { running: null, active: null, previous: null, staged: null, problem, fixed: false };

  expect(alertsOf(state({ variablesUnsaved: true }), packages)).toEqual([
    { kind: "package_not_running", problem },
    { kind: "variables_unsaved" },
  ]);
});
