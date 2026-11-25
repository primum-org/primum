# Web UI

The local web interface the board serves (Vue 3 + TypeScript, mobile first, English and
Spanish), and the only page it has. Being built through phase 5: it pairs a device and
has daily control (outputs, sequences, inputs, panic, the board's alerts); variables,
events, packages and the trace come next, then the editors. The same UI will later run
inside Primum Studio. Decision 0035.

```bash
uv run just ui-install   # its dependencies, from pnpm-lock.yaml (Node 22 or later, pnpm)
uv run just dev          # a simulated service at http://127.0.0.1:8080 ...
uv run just ui-dev       # ... and this app with hot reload, talking to it
uv run just ui-check     # lint, types, tests, build (part of `just check`)
uv run just ui-build     # build it into the runtime's package, which serves it at /
```

- **Nothing is copied here.** Texts come from `i18n/*.json` (section `webui`, errors by
  code), colors and sizes from `design/tokens/tokens.css`, icons from `design/icons/`: the
  build reads them where they are (`@i18n`, `@design`).
- **The API's types are generated.** `openapi.json` is written by `just gen` from the
  runtime's models and is in the repository; `src/generated/api.ts` is made from it at every
  build and check, and is not. `src/api/types.ts` gives the bodies their names.
- **One place talks to the board**: `src/api/client.ts`. `src/session.ts` keeps what this
  device knows of it (paired, online, the last state) and comes back by itself when the
  connection is lost.
- **Texts**: `t("key")` with the key written literally, so that the catalog test finds it.
  A key that is not used, or used and missing, fails `just check`.
- **The build is not in the repository.** It goes inside the runtime's package
  (`packages/runtime/src/primum_runtime/webui/`), which serves it; `just pi-sync` builds it
  on the laptop before copying, since the Pi has no Node, and only when it is older than
  what it is made from. Its index is served `no-cache`; its other files have their content
  in their name.
- **The board is the only source of truth.** A screen shows the state it is given and
  never guesses one; offline that state may be stale, and rows say nothing rather than
  something old. Commands go through `command()` of `src/session.ts`: the board's answer is
  its new state, and what it refuses is said above the content of every screen
  (`components/AlertStrip.vue`), with panic and the board's own alerts (`src/alerts.ts`).
- Screens have addresses after a `#`: the app works wherever the service puts it without
  the service knowing its screens.
