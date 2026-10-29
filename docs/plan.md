# Plan

Each phase ends with something working on a real Raspberry Pi 4B. Update the status column
when a phase starts or finishes.

| Phase | Goal | Status |
|---|---|---|
| 0 | Repository skeleton: structure, docs, rules, tooling, CI | In progress |
| 1 | End-to-end skeleton: toggle an LED from a phone | In progress (1.1 done) |
| 2 | Project model and `core`: workspace of files, board profile, pin conflicts, validation | Not started |
| 3 | HAL, basic drivers and safety | Not started |
| 4 | Engine: sequences, automations, events, variables, arbitration, deployment packages | Not started |
| 5 | Local web UI v1 | Not started |
| 6 | Hardware manager (`config.txt`, tryboot) and I2C, LED strip and audio drivers | Not started |
| 7 | Primum OS image | Not started |
| 8 | Local MCP server | Not started |

## Phase 0 · Repository skeleton

- [x] uv workspace with `primum-core` and `primum-runtime`
- [x] ruff, pyright (strict), pytest, import-linter, pre-commit
- [x] `justfile` with `check` (same as CI)
- [x] CI on GitHub Actions
- [x] Claude Code: `CLAUDE.md`, rules, hooks, permissions
- [x] Docs: vision, glossary, architecture, plan, decisions
- [x] Brand in `design/`: brandbook, tokens (single source) with generated CSS, logo, icons
- [ ] Development Pi with Raspberry Pi OS Lite 64-bit reachable over SSH

**Done when:** CI is green, `just check` passes locally and the development Pi is reachable.

## Phase 1 · End-to-end skeleton

The whole path, small: phone → page → API → runtime → HAL → GPIO → LED, keeping the repository's
rules from the first line. Blocks 1.1–1.3 need no Pi (simulated HAL); 1.4–1.5 need the
development Pi. One pull request per block.

**1.1 · Minimal HAL and safe state** · *no Pi* · **done**
- `primum_runtime.hal`: `Hal`, `DigitalOutput`, `OutputSpec`; `SimulatedHal` (tests,
  `--simulate`) and `GpiodHal` (libgpiod v2), chosen by `create_hal`.
- Safe state (off) when an output is created, on `apply_safe_state` and on `close`, also when
  leaving the `with` block on an exception (Ctrl+C). Crash safety (watchdog) stays in phase 3.
- `gpiod` is a Linux-only dependency, imported lazily and only by `hal/gpiod_hal.py` (an
  import contract enforces it); its own type hints pass pyright strict (decision 0010).
- Errors with codes: `hal.pin_in_use`, `hal.pin_unavailable`, `hal.closed` (catalog entries in 1.3).
- A `hw` test for the real HAL, run on the Pi with `just test-hw`.

**1.2 · Service, API and WebSocket** · *no Pi*
- FastAPI + uvicorn (pydantic at this edge only, decision 0008): `GET /api/status`,
  `PUT /api/outputs/{name}` (`{"on": true}`), `POST /api/panic`, WebSocket `/api/ws` pushing
  every state change.
- Configuration by CLI or environment: `--simulate`, pin, `active_low`, port (8080), data
  directory (default `/data`). The HAL lives in the app's lifespan, so stopping the service
  applies the safe state.
- API errors carry codes (decision 0009), for example `output.unknown`.
- `uv run just dev`: the simulated service on the laptop. Tests with the test client.

**Done when:** `uv run just dev` and `curl` or a browser toggle the simulated LED, and the
WebSocket reports every change.

**1.3 · Minimal page and i18n** · *no Pi*
- `i18n/en.json` and `es.json` created now (from phase 2): `ui.*` keys for the page and
  `errors.*` for every code so far; consistency test (same keys and placeholders in both
  catalogs, every code raised has an entry).
- A minimal page served by the runtime (HTML and a little JavaScript, no build step; Vue
  arrives in phase 5): `tokens.css`, icons from `design/`, mobile first (≥ 44 px targets),
  panic button, language from the browser, "Offline" when the service is unreachable.
  Fonts fall back to system fonts until the woff2 files arrive (phase 5).

**Done when:** from the laptop's browser the page toggles the simulated LED in English and
in Spanish.

**1.4 · Deployment to the development Pi** · *needs the Pi*
- `image/provision.sh` (idempotent): packages, `uv`, user `primum` in group `gpio`, `/data`,
  systemd unit `primum.service` (restart on failure). Nothing is set up by hand on the Pi.
- `tools/pi-sync.sh` and `just pi-sync`, `just pi-test`, `just pi-logs`, `just pi-watch`;
  host from `PRIMUM_PI_HOST` (default `dev-pi`). Claude Code permissions allow
  `uv run just pi-*` only, not raw `ssh`/`rsync`.
- Check that `gpiod` installs on Raspberry Pi OS (PyPI wheel, piwheels or build); otherwise
  fall back to the system package.

**Done when:** a phone on the same Wi-Fi opens `http://dev-pi.local:8080`, turns the LED on,
and it still works after a reboot.

**1.5 · Image spike** · *needs the Pi, half a day*
- CI builds the minimal rpi-image-gen image on an ARM runner; boot it on the Pi. Only a check
  that the tool works: the real image is phase 7.

**Watch during phase 1**
- Only LEDs, no relays: a released GPIO line may float, so relays wait for the watchdog
  (phase 3) and safe boot levels in `config.txt` (phase 6).
- Cost of the Stop hook: measure it at the end of each block; above ~10 s, limit it to the
  tests of the packages that changed.
- Scope: no sequences, automations or editor here.

## Phase 2 · Project model and `core`

1. Hand-written JSON Schemas in `schemas/` (the source, decision 0008): project manifest and
   the file types `.sec`, `.auto`, `.evt`, `.sched`, `.vars`, `.hw`; `schemaVersion` and UUIDs
   everywhere. Generated frozen dataclasses for `core`; structural validation with
   `fastjsonschema`; `just gen` and `just check` cover the generated types.
2. Error model in `core` (decision 0009): codes, params and location, added to the `i18n/`
   catalogs and to the consistency test started in phase 1.
3. Workspace loader (receives the files' contents from the caller: `core` reads no files), id references, scopes (folder visibility, export/import, redefinition
   is an error), components with parameters, cycle detection.
4. `boards/rpi4b.json`: 40 pins, alternate functions, buses, reserved pins.
5. Resource allocation and pin conflicts, reported as error codes with clear catalog messages.
6. Detection of sequences that may overlap on the same element.
7. CLI: `primum validate <project>`.

**Done when:** example projects validate, and typical conflicts are reported clearly, without the Pi.

## Phase 3 · HAL, basic drivers and safety

1. Extend the HAL started in phase 1: digital inputs, hardware PWM, crash safety.
2. Driver manifest (capabilities, config, platforms, safe state, limits, conflict policy).
3. Drivers: digital output, digital input (debounce, pull), hardware PWM.
4. Safe state on start/stop/crash, panic, test mode with expiring commands, systemd watchdog.

**Done when:** after `kill -9` of the service every output is in its safe state.

## Phase 4 · Engine and deployment packages

1. Sequence engine (monotonic clock, components flattened by the compiler).
2. Events (`.evt`), schedules (`.sched`), automations (`.auto`), runtime variables with atomic
   operations and a small, safe expression language for conditions.
3. Arbiter per element: layers by priority, latest command wins, exclusive elements,
   exclusive groups, re-trigger policy, safety on top.
4. Execution trace.
5. Deployment package: build, validate, atomic activation, rollback. Reliable-clock flag.

**Done when:** "presence sensor → 10 s sequence with relay, LED and servo" runs from a deployed
package, shows in the trace and can be rolled back.

## Phase 5 · Local web UI v1

Vue 3 + TypeScript, mobile first, English and Spanish: pairing with PIN, file explorer,
elements with *Test*, simple sequence editor with simulated preview, automations, settings
(exposed variables), daily control, alerts, "controlled by" per element.

## Phase 6 · Hardware manager

Managed block in `config.txt` (I2C, 1-Wire, PWM overlays, I2C speed, `gpio=` safe boot
lines) applied through tryboot with automatic rollback; I2C scan; drivers for MCP23017,
a BME280/VL53L0X sensor, WS2812B strip and audio.

## Phase 7 · Primum OS image

rpi-image-gen config; partitions `boot` · `rootfs A` · `rootfs B` (reserved) · `data`;
read-only root; first boot with its own Wi-Fi and setup wizard; CI publishes `.img.xz`.

## Phase 8 · Local MCP server

Tool catalogue on top of the operations (permissions, "needs confirmation"), resources,
prompts, proposals the user accepts in the UI, first evaluation set.

## After version 1

Primum Studio (Tauri) · ESP32 autonomous node and conformance suite · Arduino satellite ·
cloud (accounts, sync, licences, remote MCP) · built-in chat with the user's own key ·
Home Assistant integration over MQTT · A/B system updates.
