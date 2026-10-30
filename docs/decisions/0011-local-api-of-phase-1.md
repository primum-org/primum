# 0011. The local API of phase 1: full states, latched panic, codes for every error

- Status: Accepted
- Date: 2026-10-30

## Context
Block 1.2 adds the runtime's first service: an HTTP API and a WebSocket that the page of 1.3,
and later the web UI, the engine and Primum Studio, build on. Its shapes are hard to change
once clients exist, and two safety points had to be settled: what panic means before the
arbiter of phase 4 exists, and how stopping the service reaches the HAL.

## Decision
- **Layers** (import contracts enforce them): `cli` → `api` → `config` → `control` → `hal` →
  `errors`. FastAPI, uvicorn and pydantic live only in `api` and `cli`. The API commands
  outputs through a `Controller`, never through the HAL.
- **Endpoints**, under `/api`: `GET /status`; `PUT /outputs/{name}` with `{"on": bool}`;
  `POST /panic` and `DELETE /panic` (release); WebSocket `/ws`. Every successful response is
  the full state, `{"outputs": [{"name", "on"}], "panic"}`, outputs in configuration order.
- **The WebSocket sends full states**: the current one on connect, then one after every change.
  Each client keeps only the newest state not yet sent, so a slow client never blocks the
  controller or grows memory; it may skip intermediate states, never the latest.
- **Panic is latched** (layer 1 of decision 0006): it puts every output in its safe state and
  refuses commands with `panic.active` until it is released. It is latched before the safe
  state is tried, so it holds even if an output fails. Releasing it leaves outputs off.
- **Errors** are `{"code", "params"}` (decision 0009) with the HTTP status chosen by code:
  `output.unknown` 404, `panic.active` 409, `request.invalid` 422 (field paths in `fields`, and
  in `detail` each field's problem, never pydantic's full text, which names source files),
  `request.not_found` 404 and `request.method_not_allowed` 405 (FastAPI's own, with `path`;
  added in 1.3), `hal.closed` 503, anything else 500. Bodies are strict: `"yes"`
  or `1` are not booleans, and unknown fields are refused.
- **The HAL lives in the app's lifespan.** uvicorn turns `SIGINT` and `SIGTERM` into a
  shutdown, which closes the HAL and applies the safe state, then re-raises the signal so the
  process ends by it, as systemd expects. The log line `stopped outputs=…` is written only after
  the HAL closed without errors. A test stops a real process with `SIGTERM`.
- **Configuration** by options or `PRIMUM_*` variables (options win). The pin has no default.
  The service listens on `127.0.0.1` unless told otherwise.

## Alternatives considered
- Sending only what changed on the WebSocket: smaller, but a client that misses one message is
  wrong until it reloads; full states are a few bytes with one output, and still small with
  dozens.
- Panic as a one-off "all off": the next command turns outputs back on, which is not what
  pressing a panic button means.
- Our own signal handlers around the `with` block: uvicorn already handles both signals, and
  two handlers would race.

## Consequences
- **No authentication until phase 5** (pairing with a PIN). Anyone who reaches the port can
  command the outputs, so the default address is loopback; block 1.4 opens it to the local
  network for the phone, with LEDs only.
- Block 1.3's catalogs need entries for `output.unknown`, `panic.active` and `request.invalid`.
- The page of block 1.3 is served by the same app at `/`, after the API's routes.
- There is no data directory yet: nothing is written. It arrives with the first file the
  runtime writes, configurable and `/data` by default.
- One event loop thread runs every handler (all `async`), so the controller needs no locks.
  HAL calls are quick ioctl calls; slow drivers (phase 3) will need their own threads.
