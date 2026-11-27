// A board for tests: the state it is in, and what it was asked.

import en from "@i18n/en.json";
import { vi } from "vitest";

import type { EventState, OutputState, StateBody, VariableState } from "@/api/types";
import { Catalog, useCatalog } from "@/i18n";
import { session } from "@/session";

export const output = (over: Partial<OutputState> = {}): OutputState => ({
  id: "led",
  name: "LED",
  on: false,
  level: 0,
  actions: ["on", "off"],
  remainingMs: null,
  restFailed: false,
  controlledBy: null,
  ...over,
});

export const variable = (over: Partial<VariableState> = {}): VariableState => ({
  id: "v1",
  name: "brightness",
  type: "integer",
  value: 80,
  min: 0,
  max: 100,
  setting: true,
  persistent: false,
  ...over,
});

export const event = (over: Partial<EventState> = {}): EventState => ({
  id: "e1",
  name: "Open the shop",
  source: "ui",
  ...over,
});

// Each state a test makes is later than the ones before it, as the board's are.
let revision = 0;

export const state = (over: Partial<StateBody> = {}): StateBody => ({
  revision: ++revision,
  outputs: [],
  inputs: [],
  panic: false,
  sequences: [],
  variables: [],
  events: [],
  automations: [],
  schedules: [],
  timeKnown: true,
  variablesUnsaved: false,
  ...over,
});

export interface Asked {
  readonly method: string;
  readonly path: string;
  readonly body: unknown;
}

/** A board that is online in `initial` and answers every request with `answer` (its state
 * by default, which the test may change). Returns what it was asked, in order. */
export function board(initial: StateBody, answer: () => Response = () => json(session.state)): Asked[] {
  useCatalog(new Catalog("en", en));
  Object.assign(session, {
    pairing: { required: true, device: { id: "1", name: "phone", current: true } },
    online: true,
    state: initial,
    stateAt: performance.now(),
    problem: null,
    refused: null,
    packages: null,
    settled: true,
  });
  const asked: Asked[] = [];
  vi.stubGlobal("fetch", async (url: URL, init: RequestInit) => {
    const body: unknown = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    asked.push({ method: init.method ?? "GET", path: url.pathname, body });
    return answer();
  });
  return asked;
}

export const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status });
