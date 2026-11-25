// What the board says is not as it should be, from its state: each alert a kind and the
// names it is about. What to say of each is the screen's (components/AlertStrip.vue).

import type { PackagesBody, StateBody } from "@/api/types";
import type { ErrorLike } from "@/i18n";

export type Alert =
  | { readonly kind: "rest_failed" | "lost_events"; readonly names: readonly string[] }
  | { readonly kind: "variables_unsaved" | "time_unknown" }
  | { readonly kind: "package_not_running"; readonly problem: ErrorLike };

export function alertsOf(state: StateBody, packages: PackagesBody | null): Alert[] {
  const alerts: Alert[] = [];
  if (packages?.problem) alerts.push({ kind: "package_not_running", problem: packages.problem });
  const stuck = state.outputs.filter((output) => output.restFailed).map((output) => output.name);
  if (stuck.length > 0) alerts.push({ kind: "rest_failed", names: stuck });
  const lossy = state.inputs.filter((input) => input.lostEvents > 0).map((input) => input.name);
  if (lossy.length > 0) alerts.push({ kind: "lost_events", names: lossy });
  if (state.variablesUnsaved) alerts.push({ kind: "variables_unsaved" });
  // Only when something waits for the time: a board with no schedule needs none.
  if (!state.timeKnown && state.schedules.length > 0) alerts.push({ kind: "time_unknown" });
  return alerts;
}
