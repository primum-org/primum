// An entry of the trace as a person reads it: one sentence, from its kind and params
// (docs/specs/trace.md). The board says only codes; every word is in the catalogs, and a
// kind this app does not know yet is said as such, with its code.

import type { TraceEntry } from "@/api/types";
import { catalog, t, type Param, type Params } from "@/i18n";

const MS_PER_S = 1000;
// An unfilled {placeholder}: the message of an error whose params the entry does not carry.
const UNFILLED = /\{\w+\}/;
// The actions every switchable output has, said in words. A driver's own (a "pulse") has no
// words in the catalogs: it is named apart, never put inside a sentence of another language.
const ACTIONS: Record<string, () => string> = {
  on: () => t("trace.action.on"),
  off: () => t("trace.action.off"),
  set: () => t("trace.action.set"),
};

// What went wrong rather than what happened: these get the warning icon.
const PROBLEMS = new Set([
  "package.refused",
  "event.failed",
  "automation.failed",
  "variable.kept_value_dropped",
  "output.failed",
  "variables.unsaved",
]);

export const isProblem = (entry: TraceEntry): boolean =>
  PROBLEMS.has(entry.kind) || (entry.kind === "output.commanded" && entry.params.failed === true);

/** The sentence for an entry. */
export function traceText(entry: TraceEntry): string {
  const params: Params = entry.params;
  const name = { name: params.name ?? "" };
  switch (entry.kind) {
    case "service.started":
      return "project" in params ? t("trace.service.started", params) : t("trace.service.started_empty");
    case "package.stored":
      return t("trace.package.stored", params);
    case "package.activated":
      return params.rollback === true ? t("trace.package.activated_rollback", params) : t("trace.package.activated", params);
    case "package.refused":
      return packageRefused(params);
    case "event.happened":
      return eventHappened(params);
    case "event.ignored":
      return t("trace.event.ignored", name);
    case "event.failed":
      return t("trace.event.failed", name);
    case "automation.acted":
      return t("trace.automation.acted", name);
    case "automation.did_not_act":
      return t("trace.automation.did_not_act", name);
    case "automation.failed":
      // The automation's own problem, as its row says it: it names the automation already.
      return (
        problemOf({ ...params, automation: params.name ?? "" }) ??
        t("trace.automation.failed", { ...name, code: String(params.problem ?? "") })
      );
    case "sequence.started":
      return params.restarted === true ? t("trace.sequence.started_again", name) : t("trace.sequence.started", name);
    case "sequence.stopped":
      return sequenceStopped(params);
    case "sequence.ended":
      return t("trace.sequence.ended", name);
    case "variable.changed":
      return t("trace.variable.changed", { ...name, value: valueText(params.value) });
    case "variable.kept_value_dropped":
      return t("trace.variable.kept_value_dropped", name);
    case "output.commanded":
      return outputCommanded(params);
    case "output.released":
      return t("trace.output.released", name);
    case "output.test_ended":
      return t("trace.output.test_ended", name);
    case "output.failed":
      return t("trace.output.failed", name);
    case "output.recovered":
      return t("trace.output.recovered", name);
    case "panic.on":
      return t("trace.panic.on");
    case "panic.released":
      return t("trace.panic.released");
    case "time.known":
      return t("trace.time.known");
    case "time.unknown":
      return t("trace.time.unknown");
    case "variables.unsaved":
      return t("trace.variables.unsaved");
    case "variables.saved":
      return t("trace.variables.saved");
    default:
      // New kinds may be added to the board before this app knows them (the spec says so).
      return t("trace.unknown", { kind: entry.kind });
  }
}

// The message of the error an entry carries the code of, with the entry's params as its own;
// null when it carries none, or not the params its message needs.
function problemOf(params: Params): string | null {
  if (typeof params.problem !== "string" || params.problem === "") return null;
  const message = catalog().error({ code: params.problem, params }).message;
  return UNFILLED.test(message) ? null : message;
}

function packageRefused(params: Params): string {
  const problem = problemOf(params);
  if (problem !== null) return t("trace.package.refused", { problem });
  if (typeof params.problem === "string" && params.problem !== "")
    return t("trace.package.refused_code", { code: params.problem });
  return t("trace.package.refused_plain");
}

function eventHappened(params: Params): string {
  const name = { name: params.name ?? "" };
  switch (params.source) {
    case "ui":
      return t("trace.event.happened_ui", name);
    case "api":
      return t("trace.event.happened_api", name);
    case "schedule":
      return t("trace.event.happened_schedule", name);
    default:
      return t("trace.event.happened", name);
  }
}

function sequenceStopped(params: Params): string {
  const name = { name: params.name ?? "" };
  switch (params.by) {
    case "automation":
      return t("trace.sequence.stopped_automation", name);
    case "panic":
      return t("trace.sequence.stopped_panic", name);
    case "package":
      return t("trace.sequence.stopped_package", name);
    case "exclusive_group":
      return t("trace.sequence.stopped_group", name);
    default:
      return t("trace.sequence.stopped", name);
  }
}

function outputCommanded(params: Params): string {
  const done = commandText(params);
  return params.failed === true ? `${done} ${t("trace.output.refused")}` : done;
}

function commandText(params: Params): string {
  const name = params.name ?? "";
  const words = ACTIONS[String(params.action)];
  const tested = typeof params.durationMs === "number";
  if (words === undefined) {
    const action = String(params.action ?? "");
    return tested
      ? t("trace.output.tested_action", { name, action, seconds: seconds(Number(params.durationMs)) })
      : t("trace.output.commanded_action", { name, action });
  }
  return tested
    ? t("trace.output.tested", { name, action: words(), seconds: seconds(Number(params.durationMs)) })
    : t("trace.output.commanded", { name, action: words() });
}

// A test lasts from a second to minutes over the API, but a program may ask for less: a
// tenth of a second is kept, so that 300 ms is not said as "0 s".
const seconds = (ms: number): string =>
  new Intl.NumberFormat(catalog().language, { maximumFractionDigits: 1 }).format(ms / MS_PER_S);

function valueText(value: Param | undefined): string {
  if (value === true) return t("variable.true");
  if (value === false) return t("variable.false");
  return String(value ?? "");
}
