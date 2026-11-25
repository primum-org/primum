// What this device knows of the board: whether it is paired with it, whether the board
// answers, and its last state. The board is the only source of truth: nothing here is
// guessed, and a state is only as fresh as `online` says.

import { reactive } from "vue";

import { api, ApiError, openStates } from "@/api/client";
import type { PackagesBody, PairingBody, StateBody } from "@/api/types";
import { problemOf, type Problem } from "@/problem";

export const RECONNECT_MIN_MS = 1000;
export const RECONNECT_MAX_MS = 10000;

export const session = reactive({
  // null until the board has said it once.
  pairing: null as PairingBody | null,
  online: false,
  // Whether it is known how the connection stands: false while the first one is being
  // made, when "no connection" would be said of a connection nobody has lost yet.
  settled: false,
  state: null as StateBody | null,
  // When that state arrived, by this device's clock (`performance.now()`): what the
  // countdown of a test counts from.
  stateAt: 0,
  // Why the board could not say whether this device is paired, the last time it was asked.
  problem: null as Problem | null,
  // What the board refused the last time it was asked to do something, until dismissed.
  refused: null as Problem | null,
  // The board's packages, asked for when the connection opens: whether the active one runs.
  packages: null as PackagesBody | null,
});

let asking: Promise<boolean> | null = null;
let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;

/** Whether the board asks for a pairing code that this device has not given. */
export const mustPair = (): boolean =>
  session.pairing !== null && session.pairing.required && session.pairing.device === null;

/** Ask the board whether this device is paired. False when it could not say: it did not
 * answer, or it answered with an error, which `session.problem` then holds. Never raises
 * for either: whoever asks decides what to do without an answer. */
export function refreshPairing(): Promise<boolean> {
  // Asked once at a time: the app and its first screen both ask as they start.
  asking ??= askPairing().finally(() => {
    asking = null;
  });
  return asking;
}

async function askPairing(): Promise<boolean> {
  try {
    session.pairing = await api.pairing();
    session.problem = null;
    return true;
  } catch (failure) {
    session.problem = problemOf(failure);
    session.settled = true;
    return false;
  }
}

function take(state: StateBody): void {
  session.state = state;
  session.stateAt = performance.now();
}

/** Ask the board to do something. Its answer is its new state; what it refuses is kept in
 * `session.refused` for the screen to say. A device the board no longer knows is sent to
 * pair again. Never raises for either: a button has nothing to do with a failure. */
export async function command(asked: Promise<StateBody>): Promise<void> {
  try {
    take(await asked);
    session.refused = null;
  } catch (failure) {
    const problem = problemOf(failure);
    if (failure instanceof ApiError && failure.unpaired) {
      await connect();
      return;
    }
    // An order that did not get to the board is lost: nobody sends it again, and saying
    // "retrying" of it would be a lie. It is said as not sent until the board is back.
    session.refused = problem === "offline" ? "unsent" : problem;
  }
}

/** Pair with the board's code, then listen to its state. Raises what the board answers. */
export async function pair(code: string, name: string): Promise<void> {
  const paired = await api.pair(code, name);
  session.pairing = { required: true, device: paired.device };
  session.problem = null;
  session.settled = false;
  listen();
}

export async function unpair(): Promise<void> {
  try {
    session.pairing = await api.unpair();
  } catch (error) {
    // Unpaired already (forgotten from another device): the same end.
    if (!(error instanceof ApiError && error.unpaired)) throw error;
    session.pairing = { required: true, device: null };
  }
  stop();
}

/** Get to listening to the board's state, and stay there: ask whether this device is
 * paired and, if it is, listen. A board that cannot say (no answer, or an error) is asked
 * again, each time after a longer wait, for as long as it takes. It stops by itself only
 * when the board says this device must pair: the pairing screen takes over. */
export async function connect(delay = RECONNECT_MIN_MS): Promise<void> {
  stop();
  const known = await refreshPairing();
  if (known && mustPair()) return;
  if (known) listen(delay);
  else again(delay, Math.min(delay * 2, RECONNECT_MAX_MS));
}

/** Listen to the board's state. When the connection is lost, `connect` again: it may have
 * closed because the board stopped, or because this device was forgotten. */
export function listen(delay = RECONNECT_MIN_MS): void {
  stop();
  let opened = false;
  const current = openStates(
    (state) => {
      if (!opened) void askForPackages();
      opened = true;
      session.online = true;
      session.settled = true;
      // The board is back: an order that was not sent can be given again, and the notice
      // of it would only be in the way. What the board itself refused stays.
      if (session.refused === "unsent") session.refused = null;
      take(state);
    },
    () => {
      if (socket !== current) return; // closed on purpose, or replaced
      session.online = false;
      session.settled = true;
      // A connection that worked starts the waits over; one that never did lengthens them.
      again(delay, opened ? RECONNECT_MIN_MS : Math.min(delay * 2, RECONNECT_MAX_MS));
    },
  );
  socket = current;
}

/** Stop listening and trying, for good until `connect` or `listen` is called again. */
export function stop(): void {
  if (retry !== null) clearTimeout(retry);
  retry = null;
  const closing = socket;
  socket = null;
  closing?.close();
  session.online = false;
}

// Whether the active package runs is not in the state. Not knowing it is no problem of its
// own: the alert it would give is simply not shown.
async function askForPackages(): Promise<void> {
  session.packages = await api.packages().catch(() => null);
}

function again(after: number, next: number): void {
  retry = setTimeout(() => void connect(next), after);
}
