# Plan

Each phase ends with something working on a real Raspberry Pi 4B. Update the status column
when a phase starts or finishes.

| Phase | Goal | Status |
|---|---|---|
| 0 | Repository skeleton: structure, docs, rules, tooling, CI | In progress |
| 1 | End-to-end skeleton: toggle an LED from a phone | Not started |
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

1. Minimal FastAPI service in `primum-runtime`: `GET /api/status`, `POST /api/output`.
2. GPIO through `gpiod` (libgpiod v2): toggle one LED.
3. WebSocket with live state.
4. Minimal page served by the service, with a button.
5. systemd unit; `tools/` script to sync to the development Pi and restart it; `just pi-test`
   (sync, then `just test-hw` on the Pi).
6. Provisioning script in `image/` for everything installed on the Pi (nothing is set up by hand).
7. Half-day spike: build the minimal rpi-image-gen image in CI and boot it.

**Done when:** a phone on the same Wi-Fi turns the LED on, and it still works after a reboot.

## Phase 2 · Project model and `core`

1. Schemas (pydantic → JSON Schema in `schemas/`): project manifest and the file types
   `.sec`, `.auto`, `.evt`, `.sched`, `.vars`, `.hw`; `schemaVersion` and UUIDs everywhere.
2. Workspace loader, id references, scopes (folder visibility, export/import, redefinition
   is an error), components with parameters, cycle detection.
3. `boards/rpi4b.json`: 40 pins, alternate functions, buses, reserved pins.
4. Resource allocation and pin conflicts with clear messages.
5. Detection of sequences that may overlap on the same element.
6. CLI: `primum validate <project>`.

**Done when:** example projects validate, and typical conflicts are reported clearly, without the Pi.

## Phase 3 · HAL, basic drivers and safety

1. HAL interface with real (`gpiod`, PWM) and simulated implementations.
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
