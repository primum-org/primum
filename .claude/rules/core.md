---
paths:
  - "packages/core/**"
---

# primum-core rules

- Pure and deterministic: no hardware, network, storage, OS, processes, threads, clock,
  randomness or web frameworks (`just arch` enforces the imports). Time, ids and randomness are
  parameters.
- `uuid`, `datetime` and `pathlib` are allowed for parsing and pure paths only. Never call
  `datetime.now()`, `date.today()`, `uuid.uuid4()` or `Path` I/O in `core`: the import check
  cannot see those calls, so reviews must.
- Operations take a project and return a new project or a list of errors; they never mutate
  their input.
- Project files reference each other by id. Paths are only for display.
- Scopes: a file sees the variables of its folder and of the folders above; never siblings or
  children unless explicitly exported and imported. A name defined again in an inner scope is
  a validation error.
- Constants are resolved at compile time; runtime variables carry type, initial value,
  limits and persistence.
- Keep the public API small: it may later be reimplemented in Rust.
