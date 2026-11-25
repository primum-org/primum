// The one place that talks to the board: requests, and the WebSocket of its state.

import type { ErrorBody, PairedBody, PairingBody, StateBody } from "@/api/types";

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

// The page is served next to the API, wherever the service puts it (/app/ or /).
const url = (path: string): URL => new URL(`../api/${path}`, document.baseURI);

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = JSON_HEADERS;
    init.body = JSON.stringify(body);
  }
  let response: Response;
  try {
    response = await fetch(url(path), init);
  } catch (cause) {
    throw new OfflineError("the board did not answer", { cause });
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
};

/** The WebSocket of the board's state: the current one on connect, then every new one. */
export function openStates(onState: (state: StateBody) => void, onClose: () => void): WebSocket {
  const address = url("ws");
  address.protocol = address.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(address);
  socket.addEventListener("message", (event: MessageEvent<string>) => {
    onState(JSON.parse(event.data) as StateBody);
  });
  socket.addEventListener("close", onClose);
  return socket;
}
