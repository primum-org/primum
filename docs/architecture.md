# Architecture

## Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Interfaces      web UI (on the board) · Primum Studio · MCP · chat   │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. Project model   files, ids, scopes, elements, capabilities           │
│                    (hardware independent)                               │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. Compiler        resolve (ids, components, scopes) → validate →       │
│                    split between boards → one flat package per board    │
├────────────────────────────────┬────────────────────────────────────────┤
│ 4. Board profiles (data)       │ 5. Drivers: manifest + one             │
│    pins, buses, resources      │    implementation per platform         │
├────────────────────────────────┴────────────────────────────────────────┤
│ 6. Deployment and transports   package format · HTTP · USB serial ·     │
│                                 MQTT · later RS-485, LoRa…              │
├─────────────────────────────────────────────────────────────────────────┤
│ 7. Runtimes   Linux (Python) · ESP32/RP2040 (C++) · AVR satellite (C++) │
│               engine · arbiter · HAL · drivers · safety · storage       │
├─────────────────────────────────────────────────────────────────────────┤
│ 8. Coordination   event bus · clock sync · heartbeats · safe fallback   │
├─────────────────────────────────────────────────────────────────────────┤
│ 9. Cloud (optional)   accounts · licences · sync · fleet · AI           │
└─────────────────────────────────────────────────────────────────────────┘
```

Layers 2–5 are `primum-core` (pure). Layer 7 for Linux is `primum-runtime`. Version 1
implements one target (Raspberry Pi 4B) with this structure already in place.

## Packages and where they run

| Package | Pi | Primum Studio | Backend |
|---|---|---|---|
| `primum-core` (model, validation, operations, compiler, simulator) | ✓ | ✓ (sidecar) | ✓ |
| `schemas/` and generated types | ✓ | ✓ | ✓ |
| `apps/webui` | ✓ (local web) | ✓ (inside Tauri) | optional |
| `primum-runtime` (engine, HAL, drivers, safety) | ✓ | — | — |

The backend never runs sequences on hardware; it uses `core` to validate, apply operations,
compile packages and simulate.

## Key flows

**Editing.** Every change is a `core` operation (project in → project or errors out). The
web UI, Primum Studio, the MCP server and the backend call the same operations.

**Deploying.** Project folder → resolve → validate → split by board → flat package per
board (with hash and minimum runtime version) → the board validates it again against its
real hardware → atomic activation, with rollback to the previous package.

**Running.** Events (sensors, time, buttons, API) → automations → sequences → the arbiter of
each element (on the board it is wired to) → driver → HAL. Safety sits above everything.

## Boundaries enforced by tools

- `core` imports nothing from `runtime`, hardware, network or web frameworks (`just arch`).
- Generated files are never edited by hand (Claude Code hook + CI).

## Further reading

- `glossary.md` for the vocabulary.
- `decisions/` for why things are the way they are.
- `specs/` for the exact behaviour (filled in from phase 2).
