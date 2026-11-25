// What this device knows of the board: whether it is paired with it, whether the board
// answers, and its last state. The board is the only source of truth: nothing here is
// guessed, and a state is only as fresh as `online` says.

import { reactive } from "vue";

import { api, ApiError, OfflineError, openStates } from "@/api/client";
import type { PairingBody, StateBody } from "@/api/types";

export const RECONNECT_MIN_MS = 1000;
export const RECONNECT_MAX_MS = 10000;

export const session = reactive({
  // null until the board has been asked once.
  pairing: null as PairingBody | null,
  online: false,
  state: null as StateBody | null,
});

let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;

/** Whether the board asks for a pairing code that this device has not given. */
export const mustPair = (): boolean =>
  session.pairing !== null && session.pairing.required && session.pairing.device === null;

/** Ask the board whether this device is paired. False when it does not answer. */
export async function refreshPairing(): Promise<boolean> {
  try {
    session.pairing = await api.pairing();
    return true;
  } catch (error) {
    if (error instanceof OfflineError) return false;
    throw error;
  }
}

/** Pair with the board's code, then listen to its state. Raises what the board answers. */
export async function pair(code: string, name: string): Promise<void> {
  const paired = await api.pair(code, name);
  session.pairing = { required: true, device: paired.device };
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

/** Listen to the board's state for as long as this device is paired, coming back by
 * itself when the connection is lost, each time after a longer wait. */
export function listen(delay = RECONNECT_MIN_MS): void {
  stop();
  let opened = false;
  const current = openStates(
    (state) => {
      opened = true;
      session.online = true;
      session.state = state;
    },
    () => {
      if (socket !== current) return; // closed on purpose, or replaced
      session.online = false;
      const next = opened ? RECONNECT_MIN_MS : Math.min(delay * 2, RECONNECT_MAX_MS);
      retry = setTimeout(() => void comeBack(next), delay);
    },
  );
  socket = current;
}

/** Stop listening, for good until `listen` is called again. */
export function stop(): void {
  if (retry !== null) clearTimeout(retry);
  retry = null;
  const closing = socket;
  socket = null;
  closing?.close();
  session.online = false;
}

// The connection may have closed because the board stopped, or because this device was
// forgotten: the board is asked before trying again.
async function comeBack(delay: number): Promise<void> {
  retry = null;
  const answered = await refreshPairing();
  if (answered && mustPair()) return; // the pairing screen takes over
  listen(delay);
}
