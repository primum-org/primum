# primum-core

The pure library shared by the runtime, the desktop app (Primum Studio) and the backend.

- No imports of hardware, network, storage, subprocess, asyncio or web frameworks
  (`just arch` fails otherwise). Standard library and small pure dependencies only.
- Deterministic: the same input gives the same output. Time, ids and randomness are
  parameters, never read from the system.
- Public API stays small and stable: it may later be reimplemented in Rust (PyO3/WASM)
  without changing callers.
- Errors are values with a stable `code`, a human message and a `hint` (users and AI read them).
- Everything here is tested without the Pi.
