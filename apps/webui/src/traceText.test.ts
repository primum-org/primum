import en from "@i18n/en.json";
import es from "@i18n/es.json";
import { afterEach, expect, test } from "vitest";

import type { TraceEntry } from "@/api/types";
import { Catalog, useCatalog } from "@/i18n";
import { isProblem, traceText } from "@/traceText";

const entry = (kind: string, params: TraceEntry["params"] = {}): TraceEntry => ({
  number: 1,
  atMs: 0,
  time: null,
  kind,
  params,
  cause: null,
});
const NAMED = { id: "x", name: "Welcome" };

// Every kind of docs/specs/trace.md, with the params it has there.
const EVERY_KIND: TraceEntry[] = [
  entry("service.started", { project: "Shop window", package: "abc" }),
  entry("service.started"),
  entry("package.stored", { project: "Shop window", package: "abc" }),
  entry("package.activated", { project: "Shop window", package: "abc", previous: "def" }),
  entry("package.activated", { project: "Shop window", package: "def", previous: "abc", rollback: true }),
  entry("package.refused", { hash: "abc", problem: "panic.active" }),
  ...["element", "ui", "api", "schedule"].map((source) => entry("event.happened", { ...NAMED, source })),
  entry("event.ignored", { ...NAMED, source: "element", reason: "panic" }),
  entry("event.failed", { ...NAMED, source: "element" }),
  entry("automation.acted", NAMED),
  entry("automation.did_not_act", NAMED),
  entry("automation.failed", { ...NAMED, problem: "automation.condition_failed", reason: "x" }),
  entry("sequence.started", { ...NAMED, by: "automation" }),
  entry("sequence.started", { ...NAMED, by: "api", restarted: true }),
  ...["api", "automation", "panic", "package", "exclusive_group"].map((by) => entry("sequence.stopped", { ...NAMED, by })),
  entry("sequence.ended", NAMED),
  entry("variable.changed", { ...NAMED, value: 3, by: "api" }),
  entry("variable.kept_value_dropped", { ...NAMED, problem: "variable.value_invalid" }),
  entry("output.commanded", { ...NAMED, action: "on" }),
  entry("output.commanded", { ...NAMED, action: "set", durationMs: 5000, failed: true }),
  entry("output.released", NAMED),
  entry("output.test_ended", NAMED),
  entry("output.failed", NAMED),
  entry("output.recovered", NAMED),
  entry("panic.on"),
  entry("panic.released"),
  entry("time.known"),
  entry("time.unknown"),
  entry("variables.unsaved"),
  entry("variables.saved"),
];

afterEach(() => useCatalog(new Catalog("en", en)));

test.each([
  ["en", en],
  ["es", es],
] as const)("every kind has its own sentence in %s, with every placeholder filled", (language, messages) => {
  useCatalog(new Catalog(language, messages));
  const unknown = new Catalog(language, messages).t("trace.unknown", { kind: "" }).slice(0, 10);

  for (const each of EVERY_KIND) {
    const text = traceText(each);
    expect(text, each.kind).not.toContain("{");
    expect(text.startsWith(unknown), each.kind).toBe(false);
    expect(text, each.kind).not.toContain("trace.");
  }
});

test("sentences say what happened, with names and values", () => {
  useCatalog(new Catalog("en", en));

  expect(traceText(entry("automation.acted", NAMED))).toBe("Welcome acted.");
  expect(traceText(entry("event.happened", { ...NAMED, source: "ui" }))).toBe("Welcome was fired from the app.");
  expect(traceText(entry("variable.changed", { ...NAMED, value: true }))).toBe("Welcome is now Yes.");
  expect(traceText(entry("output.commanded", { ...NAMED, action: "on", durationMs: 5000 }))).toBe(
    "Welcome was told to turn on, as a test for 5 s.",
  );
  expect(traceText(entry("package.refused", { hash: "abc", problem: "panic.active" }))).toMatch(
    /^A project could not be activated: .*[Pp]anic/,
  );
});

test("in Spanish too", () => {
  useCatalog(new Catalog("es", es));

  expect(traceText(entry("sequence.stopped", { ...NAMED, by: "exclusive_group" }))).toBe(
    "Welcome se paró: empezó otra secuencia de su grupo.",
  );
  expect(traceText(entry("output.commanded", { ...NAMED, action: "off" }))).toBe("Se mandó apagar Welcome, a mano.");
});

test("a kind this app does not know yet is said as such, with its code", () => {
  expect(traceText(entry("motor.stalled", NAMED))).toBe("Something this app cannot describe yet (motor.stalled).");
});

test("what went wrong is told apart from what happened", () => {
  expect(isProblem(entry("automation.failed", NAMED))).toBe(true);
  expect(isProblem(entry("output.commanded", { ...NAMED, action: "on", failed: true }))).toBe(true);
  expect(isProblem(entry("output.commanded", { ...NAMED, action: "on" }))).toBe(false);
  expect(isProblem(entry("automation.did_not_act", NAMED))).toBe(false);
});
