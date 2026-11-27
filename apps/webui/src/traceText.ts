// An entry of the trace as a person reads it: one sentence, from its kind and params
// (docs/specs/trace.md). The board says only codes; every word is in the catalogs, and a
// kind this app does not know yet is said as such, with its code.

import type { TraceEntry } from "@/api/types";
import { catalog, t, type Param, type Params } from "@/i18n";

const MS_PER_S = 1000;

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
      return t("trace.package.refused", { problem: problemOf(params) });
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
      return problemOf({ ...params, automation: params.name ?? "" });
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

// The message of the error an entry carries the code of, with the entry's params as its own.
const problemOf = (params: Params): string =>
  catalog().error({ code: String(params.problem ?? ""), params }).message;

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
  const name = params.name ?? "";
  const action = actionText(params.action);
  const done =
    typeof params.durationMs === "number"
      ? t("trace.output.tested", { name, action, seconds: Math.round(params.durationMs / MS_PER_S) })
      : t("trace.output.commanded", { name, action });
  return params.failed === true ? `${done} ${t("trace.output.refused")}` : done;
}

// The actions every switchable output has are said in words; the others are a driver's
// own, and keep their name.
function actionText(action: Param | undefined): string {
  if (action === "on") return t("trace.action.on");
  if (action === "off") return t("trace.action.off");
  if (action === "set") return t("trace.action.set");
  return String(action ?? "");
}

function valueText(value: Param | undefined): string {
  if (value === true) return t("variable.true");
  if (value === false) return t("variable.false");
  return String(value ?? "");
}
