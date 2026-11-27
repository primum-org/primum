// The one place that talks to the board: requests, and the WebSockets of its state and its
// trace.

import type {
  DeviceBody,
  ErrorBody,
  PackagesBody,
  PairedBody,
  PairingBody,
  StateBody,
  TraceBody,
} from "@/api/types";

// The status of a request from a device that is not paired with the board.
const UNPAIRED = 401;
const JSON_HEADERS = { "Content-Type": "application/json" };

/** What the board answered instead of what was asked: a code and its params, never text. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly params: ErrorBody["params"],
  ) {
    super(code);
  }

  get unpaired(): boolean {
    return this.status === UNPAIRED;
  }
}

/** The board did not answer at all: no network, or the service is stopped. */
export class OfflineError extends Error {}

/** The board took the request and did not answer in time: nobody knows whether it did
 * what was asked. A board that is frozen, or out of reach without the connection closing. */
export class UnansweredError extends Error {}

// How long the board is waited for. It answers in milliseconds: past this, a person must
// be told that nothing came back instead of being left looking at a screen that says nothing.
export const COMMAND_TIMEOUT_MS = 5000;
// Activating a package stops what runs, reads and checks the package again and starts it:
// about a second for a show of 3000 clips on a laptop, several on a Pi. Waited for longer,
// so that a slow activation is not said as an order nobody knows the end of.
export const ACTIVATION_TIMEOUT_MS = 30000;

// The API is served next to the app, wherever the service puts both.
const url = (path: string): URL => new URL(`api/${path}`, document.baseURI);

type Arguments = Readonly<Record<string, number | boolean | string>>;
const id = encodeURIComponent;

async function request<T>(method: string, path: string, body?: unknown, timeoutMs = COMMAND_TIMEOUT_MS): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = JSON_HEADERS;
    init.body = JSON.stringify(body);
  }
  const waiting = new AbortController();
  let late = false;
  const timer = setTimeout(() => {
    late = true;
    waiting.abort();
  }, timeoutMs);
  init.signal = waiting.signal;
  let response: Response;
  try {
    response = await fetch(url(path), init);
  } catch (cause) {
    if (late) throw new UnansweredError("the board did not answer in time", { cause });
    throw new OfflineError("the board did not answer", { cause });
  } finally {
    clearTimeout(timer);
  }
  // An unexpected failure may not be JSON: its HTTP status stands in for the code.
  const payload: unknown = await response.json().catch(() => null);
  if (response.ok) return payload as T;
  const error = payload as Partial<ErrorBody> | null;
  throw new ApiError(response.status, error?.code ?? `http.${response.status}`, error?.params ?? {});
}

export const api = {
  pairing: () => request<PairingBody>("GET", "pairing"),
  pair: (code: string, name: string) => request<PairedBody>("POST", "pairing", { code, name }),
  unpair: () => request<PairingBody>("DELETE", "pairing"),
  packages: () => request<PackagesBody>("GET", "package"),
  /** Run a package the board keeps, by its hash: everything stops first. */
  activatePackage: (hash: string) =>
    request<PackagesBody>("POST", "package/activate", { hash }, ACTIVATION_TIMEOUT_MS),
  /** Run again the package that ran before the active one: the two swap. */
  rollbackPackage: () => request<PackagesBody>("POST", "package/rollback", undefined, ACTIVATION_TIMEOUT_MS),
  devices: () => request<DeviceBody[]>("GET", "pairing/devices"),
  /** Forget a paired device: its token is worth nothing from now on. Answers with those left. */
  forgetDevice: (device: string) => request<DeviceBody[]>("DELETE", `pairing/devices/${id(device)}`),
  // Every command answers with the board's whole state after it.
  /** Ask an output for one of the actions of its driver, with the arguments it takes by
   * name. With a duration it is a test: the output goes to rest on its own after it. */
  ask: (output: string, action: string, args: Arguments = {}, durationMs: number | null = null) =>
    request<StateBody>("PUT", `outputs/${id(output)}`, { action, arguments: args, durationMs }),
  /** Give an output a person holds back to the sequences. */
  release: (output: string) => request<StateBody>("DELETE", `outputs/${id(output)}`),
  startSequence: (sequence: string) => request<StateBody>("POST", `sequences/${id(sequence)}/start`),
  stopSequence: (sequence: string) => request<StateBody>("POST", `sequences/${id(sequence)}/stop`),
  /** Give a variable a value, of its type and within its limits: the board checks both. */
  setVariable: (variable: string, value: number | boolean | string) =>
    request<StateBody>("PUT", `variables/${id(variable)}`, { value }),
  /** Make an event happen by hand: its automations act. */
  fireEvent: (event: string) => request<StateBody>("POST", `events/${id(event)}/fire`),
  panic: () => request<StateBody>("POST", "panic"),
  releasePanic: () => request<StateBody>("DELETE", "panic"),
};

/** The WebSocket of the board's state: the current one on connect, then every new one. */
export function openStates(onState: (state: StateBody) => void, onClose: () => void): WebSocket {
  return openSocket(url("ws"), onState, onClose);
}

/** The WebSocket of the board's trace: what it keeps above entry `after` on connect (also
 * when that is nothing), then each new entry or entries as they are noted. */
export function openTrace(after: number, onBody: (body: TraceBody) => void, onClose: () => void): WebSocket {
  const address = url("trace/ws");
  address.searchParams.set("after", String(after));
  return openSocket(address, onBody, onClose);
}

function openSocket<T>(address: URL, onMessage: (body: T) => void, onClose: () => void): WebSocket {
  address.protocol = address.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(address);
  socket.addEventListener("message", (event: MessageEvent<string>) => {
    onMessage(JSON.parse(event.data) as T);
  });
  socket.addEventListener("close", onClose);
  return socket;
}
