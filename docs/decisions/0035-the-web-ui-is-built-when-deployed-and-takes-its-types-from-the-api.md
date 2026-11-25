# 0035. The web UI is built when it is deployed, and takes the API's types from its models

- Status: Accepted
- Date: 2026-11-25

## Context
Block 5.2 starts `apps/webui`, the Vue app that replaces the page of phase 1. That page has
no build step: its files are served as they are. A Vue app has one, and a Raspberry Pi has
no Node to run it. The app also needs the shapes of the API's bodies, which exist only as
pydantic models in the runtime, and the same texts, tokens and icons as everything else.

## Decision
- **The build is not in the repository.** `just ui-build` writes it inside the runtime's
  package (`primum_runtime/webui/`), ignored by git, and the service serves it if it is
  there. `just pi-sync` builds on the laptop and copies the build with the source; the wheel
  takes it as an artifact. CI builds it to know that it builds.
- **Next to the page until it can replace it**: the app is served at `/app/` and the page
  stays at `/`. Block 5.3 moves the app to `/` and removes the page. The app is built with
  relative addresses and keeps its screens after a `#`, so the move is the service's alone.
- **The API's types come from the runtime's models.** `just gen` writes what FastAPI derives
  from them to `apps/webui/openapi.json`, which is in the repository and checked by
  `just check`; the TypeScript types are made from it at every build and never kept. The
  service still serves no description of itself (decision 0034).
- **Shared sources are read, not copied**: the catalogs of `i18n/` (a `webui` section, and
  the errors by code), `design/tokens/tokens.css` and `design/icons/`.
- **Tools**: pnpm with a lockfile; Vite; Vitest; Vue Router; a small layer of our own over
  the catalogs instead of an i18n library; no store library until shared state asks for one.

## Alternatives considered
- Keeping the build in the repository, like the copies under `ui/generated/`: deploying
  would not change, but every pull request of the UI would carry compiled files with hashed
  names, and checking that they are up to date depends on two versions of Node giving the
  same bytes.
- Replacing the page at once: one frontend, but a board without switches or a panic button
  on its page until 5.3.
- JSON Schemas for the API's bodies (decision 0008 makes schemas the source of every
  *format*): the bodies are not a format anyone stores or exchanges, and schemas written by
  hand next to the pydantic models would be two sources of one thing.
- Types written by hand: nothing says when the API changes under them.
- `vue-i18n`: the catalogs have their own shape (errors by code with message and hint,
  lists formatted for the language, technical params apart), already solved in a few lines.

## Consequences
- Deploying to the Pi needs Node and pnpm on the laptop. A service installed from a
  checkout that was not built has no web UI, starts all the same and says so in its log.
- Changing a body of the API changes `openapi.json` in the same pull request, where a
  reviewer sees it, and the UI's type check fails where it no longer fits.
- TypeScript types of the project's formats (from `schemas/`, decision 0008) are still to
  come: with the first screen that edits a project (block 5.4).
- The catalogs have two sections of UI texts, `ui` (the page) and `webui`, until 5.3
  removes the first.

## Since
- Block 5.3a (2026-11-25): the app is served at `/` and the page of phase 1 is gone, with
  its copies of the catalogs and the brand under `ui/generated/`, its tests and the `ui`
  section of the catalogs. A service whose web UI was not built has no page.
