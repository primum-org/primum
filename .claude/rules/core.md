---
paths:
  - "packages/core/**"
---

# primum-core rules

- Pure and deterministic: no hardware, network, storage, files, OS, interpreter state, locale,
  processes, threads, clock, randomness, logging or web frameworks (`just arch` enforces the
  imports). Time, ids, randomness and any data from disk (board profiles, manifests) are
  parameters: callers load them.
- `uuid`, `datetime` and `pathlib` are allowed for parsing and pure paths only. Never call
  `datetime.now()`, `date.today()` or `uuid.uuid4()`, and never use the concrete `Path` class
  (use `PurePosixPath`). The import check cannot see those names;
  `packages/core/tests/test_purity.py` resolves imports (aliases included) and rejects them.
- Operations take a project and return a new project or a list of errors; they never mutate
  their input.
- Project files reference each other by id. Paths are only for display.
- Scopes: a file sees the variables of its folder and of the folders above; never siblings or
  children unless explicitly exported and imported. A name defined again in an inner scope is
  a validation error.
- Constants are resolved at compile time; runtime variables carry type, initial value,
  limits and persistence.
- Keep the public API small: it may later be reimplemented in Rust.
