---
paths:
  - "packages/core/**"
---

# primum-core rules

- Pure and deterministic: no hardware, network, storage, subprocess, asyncio, threads or
  web frameworks (`just arch` enforces it). Time, ids and randomness are parameters.
- Operations take a project and return a new project or a list of errors; they never mutate
  their input.
- Project files reference each other by id. Paths are only for display.
- Scopes: a file sees the variables of its folder and of the folders above; never siblings or
  children unless explicitly exported and imported. A name defined again in an inner scope is
  a validation error.
- Constants are resolved at compile time; runtime variables carry type, initial value,
  limits and persistence.
- Keep the public API small: it may later be reimplemented in Rust.
