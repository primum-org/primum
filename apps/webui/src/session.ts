// What this device knows of the board: whether it is paired with it, whether the board
// answers, and its last state. The board is the only source of truth: nothing here is
// guessed, and a state is only as fresh as `online` says.

import { reactive } from "vue";

import { api, ApiError, openStates } from "@/api/client";
import type { PackagesBody, PairingBody, StateBody } from "@/api/types";
import type { ErrorLike } from "@/i18n";
import { problemOfAsking, problemOfOrder, type Problem } from "@/problem";

export const RECONNECT_MIN_MS = 1000;
export const RECONNECT_MAX_MS = 10000;
// A board that is there says its state again every 2 s when nothing changes. One that is
// frozen, or out of the Wi-Fi's reach, closes nothing: three beats without a word and it
// is taken for gone.
export const SILENCE_MS = 6000;

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
  // Why the board could not say whether this device is paired, the last time it was asked:
  // an error of its own, or that it is out of reach. Never an order left undone.
  problem: null as ErrorLike | "offline" | null,
  // What the board refused the last time it was asked to do something, until dismissed.
  refused: null as Problem | null,
  // The board's packages, asked for when the connection opens: whether the active one runs.
  packages: null as PackagesBody | null,
});

let asking: Promise<boolean> | null = null;
let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;
let silence: ReturnType<typeof setTimeout> | null = null;

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
    session.problem = problemOfAsking(failure);
    session.settled = true;
    return false;
  }
}

// States reach this device by two ways, the answer to a command and the WebSocket, and may
// cross on their way: the board numbers them, and one that is not later than the one held
// is dropped. A new connection may be to a board that was restarted and counts from one
// again: its first state is believed whatever its number.
function take(state: StateBody, fresh = false): void {
  if (!fresh && session.state !== null && state.revision <= session.state.revision) return;
  const changed = session.state === null || !sameState(state, session.state);
  session.state = state;
  session.stateAt = performance.now();
  // The packages are asked for apart, and go stale: a new state may be of a package another
  // device has just activated. Asked again for the alert of a package that does not run,
  // and while a screen shows them; not on a beat that says the same again: every 2 s, for
  // as long as the package does not run, nobody asked for.
  if (changed && (session.packages?.problem || packagesShown > 0)) askForPackagesSoon();
}

// At most this often from new states: a sequence running changes the state several times
// a second, and asking at each would have a phone left on a screen ask all through a show.
export const PACKAGES_MIN_INTERVAL_MS = 3000;
let packagesAskedAt = Number.NEGATIVE_INFINITY;
let packagesLater: ReturnType<typeof setTimeout> | null = null;

// Ask for the packages now, or as soon as the interval allows: once, for every change
// meanwhile, so that the last one is not missed.
function askForPackagesSoon(): void {
  if (packagesLater !== null) return;
  // By the clock that never jumps: a phone whose time is set back would wait for long.
  const wait = packagesAskedAt + PACKAGES_MIN_INTERVAL_MS - performance.now();
  if (wait <= 0) {
    void askForPackages();
    return;
  }
  packagesLater = setTimeout(() => {
    packagesLater = null;
    void askForPackages();
  }, wait);
}

// How many screens show the packages now.
let packagesShown = 0;

/** Keep `session.packages` fresh while a screen shows them: asked for now, and again with
 * every state that says something new. Returns what to call when the screen goes. */
export function showPackages(): () => void {
  packagesShown += 1;
  void refreshPackages();
  return () => {
    packagesShown -= 1;
  };
}

// Whether two states say the same, whatever their numbers.
const sameState = (one: StateBody, other: StateBody): boolean =>
  JSON.stringify({ ...one, revision: 0 }) === JSON.stringify({ ...other, revision: 0 });

/** The board no longer knows this device: the pairing screen takes over (main.ts), and
 * says why. Found by an order, what was asked was not done, and is said so; found by a
 * question asked by itself (`ordered` false), nobody asked for anything. */
export async function forgotten(ordered = true): Promise<void> {
  session.refused = ordered ? "forgotten" : "unpaired";
  await connect();
}

/** Ask the board to do something, and say whether it did. Its answer is its new state;
 * what it refuses is kept in `session.refused` for the screen to say. A device the board
 * no longer knows is sent to pair again. Never raises for either: a button has nothing to
 * do with a failure. */
export async function command(asked: Promise<StateBody>): Promise<boolean> {
  try {
    take(await asked);
    session.refused = null;
    // The board answered: it is there, whatever the wait to try the connection again
    // says. Connect now, so that the screen stops saying it has none.
    if (!session.online) void connect();
    return true;
  } catch (failure) {
    const problem = problemOfOrder(failure);
    if (failure instanceof ApiError && failure.unpaired) {
      await forgotten();
      return false;
    }
    // An order that did not get to the board is lost: nobody sends it again, and saying
    // "retrying" of it would be a lie. It is said as not sent until the board is back.
    session.refused = problem;
    // A board that does not answer is not to be taken for connected, whatever the
    // WebSocket says (nothing tells a frozen board from a quiet one): connect again.
    if (problem === "unanswered") void connect();
    return false;
  }
}

/** Pair with the board's code, then listen to its state. Raises what the board answers. */
export async function pair(code: string, name: string): Promise<void> {
  const paired = await api.pair(code, name);
  session.pairing = { required: true, device: paired.device };
  session.problem = null;
  session.refused = null;
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
  // Counted from now: a connection that opens and never says anything is given up too.
  hear();
  const current = openStates(
    (state) => {
      hear();
      if (!opened) void askForPackages();
      session.online = true;
      session.settled = true;
      // The board is back: an order that was not sent can be given again, and the notice
      // of it would only be in the way. What the board itself refused stays, and so does
      // an order nobody knows the end of: the person must look.
      if (!opened && session.refused === "unsent") session.refused = null;
      take(state, !opened);
      opened = true;
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

// The board said something, or is given this long to: silence past it means it is gone,
// whatever the connection says, and it is looked for again.
function hear(): void {
  if (silence !== null) clearTimeout(silence);
  silence = setTimeout(() => {
    session.settled = true;
    void connect();
  }, SILENCE_MS);
}

/** Stop listening and trying, for good until `connect` or `listen` is called again. */
export function stop(): void {
  if (retry !== null) clearTimeout(retry);
  retry = null;
  if (silence !== null) clearTimeout(silence);
  silence = null;
  if (packagesLater !== null) clearTimeout(packagesLater);
  packagesLater = null;
  const closing = socket;
  socket = null;
  closing?.close();
  session.online = false;
}

// Whether the active package runs is not in the state. Not knowing it is no problem of its
// own: the alert it would give is simply not shown, and what was known stays until the
// board answers again. Asked once at a time.
let askingPackages = false;
let askAgain = false;

/** Ask the board for its packages now: a screen that shows them, a connection back. */
export const refreshPackages = (): Promise<void> => askForPackages();

async function askForPackages(): Promise<void> {
  // Asked while an answer is on its way: what changed meanwhile may not be in it.
  if (askingPackages) {
    askAgain = true;
    return;
  }
  askingPackages = true;
  packagesAskedAt = performance.now();
  try {
    session.packages = await api.packages();
  } catch (failure) {
    if (failure instanceof ApiError && failure.unpaired) await forgotten(false);
  } finally {
    askingPackages = false;
  }
  if (askAgain) {
    askAgain = false;
    await askForPackages();
  }
}

function again(after: number, next: number): void {
  retry = setTimeout(() => void connect(next), after);
}
