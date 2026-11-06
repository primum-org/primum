# primum-core

The pure library at the heart of Primum: project model, validation, pin conflicts,
compiler and simulator. Shared by the runtime (Pi), the desktop app and the backend.

It has no hardware, network, storage or clock dependencies: callers read files and pass their
content. See `CLAUDE.md` in this folder and `docs/architecture.md`.

- `formats`: read a file (bytes) into its typed value, or the issues that prevent it.
- `errors`: `Issue`, `CoreErrorCode`, `Location`, `Severity` (codes, never text: decision 0009).
- `workspace`: read a whole project (`load_workspace(files, profiles)`) and check it: ids and
  references, scopes of names and components, the resources of each board.
- `generated/`: the schemas and the dataclasses generated from `schemas/` (`uv run just gen`).
