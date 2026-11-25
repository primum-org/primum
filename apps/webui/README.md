# Web UI

The local web interface the board serves (Vue 3 + TypeScript, mobile first, English and
Spanish). Being built through phase 5: for now it pairs a device and says whether the board
answers; the page of phase 1 (`primum_runtime/ui/`) still has the controls, and block 5.3
replaces it. The same UI will later run inside Primum Studio. Decision 0035.

```bash
uv run just ui-install   # its dependencies, from pnpm-lock.yaml (Node 22 or later, pnpm)
uv run just dev          # a simulated service at http://127.0.0.1:8080 ...
uv run just ui-dev       # ... and this app with hot reload, talking to it
uv run just ui-check     # lint, types, tests, build (part of `just check`)
uv run just ui-build     # build it into the runtime's package: served at /app/
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
  on the laptop before copying, since the Pi has no Node.
- Screens have addresses after a `#`: the app works wherever the service puts it without
  the service knowing its screens.
