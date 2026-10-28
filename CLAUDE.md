# CLAUDE.md

Primum lets people who do not program bring hardware to life: they create **sequences**
(actions placed in time, on tracks) and **automations** (when → if → do) for lights,
motors, sensors and sound, and run them locally on a Raspberry Pi (later also ESP32 and
Arduino). No Internet required.

Read first: `docs/vision.md` (scope) · `docs/glossary.md` (vocabulary) ·
`docs/architecture.md` (layers) · `docs/plan.md` (phases and **current status**).

## Invariants (never break these)

- `primum-core` is pure: no hardware, network, storage, subprocesses or system clock.
  Time, randomness and ids enter as parameters. Enforced by `just arch`.
- Every project edit is a `core` operation: takes a project, returns a new project or errors.
  APIs, the MCP server and the UI call operations; they never edit project data themselves.
- Files of a project reference each other by **id**, never by path.
- The runtime never sees folders or scopes: it receives a flat, validated deployment package.
- Schemas in `schemas/` are the single source; Python and TypeScript types are generated.
  Generated files are never edited by hand (a hook blocks it).
- No driver without a safe state, limits and a test against the simulated HAL.
- Each output has a single arbiter, on the board it is wired to. Safety (panic, safe state,
  driver limits) is above any priority.
- Sequences never emit events. Events come only from outside (sensors, time, buttons, API).
- Variables change only through atomic operations (set, increment), never read-modify-write.
- AI (MCP or chat) never deploys or moves hardware without the user confirming it.
- A breaking change to a file format bumps `schemaVersion` and ships a migration with a test.
- Colors, fonts, sizes, radii, spacing and motion come only from `design/tokens/tokens.json`;
  `tokens.css` is generated from it (`just gen`).

## Layout

```
packages/core      primum-core: model, validation, compiler, simulator (pure)
packages/runtime   primum-runtime: engine, HAL, drivers, safety, local API (Linux/Pi)
apps/webui         local web UI (Vue 3 + TypeScript), from phase 5
schemas/           JSON Schemas: single source of the formats
boards/            board profiles (pins, peripherals, resources)
design/            brand: brandbook, tokens (single source), logo, icons
image/             Primum OS image (rpi-image-gen), from phase 7
tools/             developer scripts
docs/              vision, glossary, architecture, plan, specs/, decisions/
```

## Commands

`just` lists every task. Main ones: `just check` (everything CI runs: lint, types,
architecture, generated files, tests) · `just test` · `just watch` (tests on save) ·
`just fmt` · `just gen` (regenerate generated files) · `just sync` (install from `uv.lock`).
Dependencies: `uv add <pkg> --package primum-core`.

## Before you…

- change the engine or arbitration → read `docs/specs/` (engine semantics) and the
  decisions in `docs/decisions/`.
- make a design choice that others will rely on → add a note in `docs/decisions/`.
- add a dependency to `core` → don't, unless it is pure and small; ask first.
- build or style UI → read `design/README.md` (tokens, reserved colors, type, icons, voice).

## Conventions

- Code, identifiers, comments, docs and commits in **English**. UI text goes through i18n:
  English is the default locale, Spanish the second one.
- Conventional Commits (`feat(core): …`, `fix(runtime): …`, `docs: …`).
- Detailed rules load automatically per folder from `.claude/rules/`.

## When you finish a task

`just check` is green · specs/docs updated if behaviour changed · `CHANGELOG.md`
updated if a user would notice · `docs/plan.md` status updated if a phase item is done.
