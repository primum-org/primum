# Specifications

Exact, testable descriptions of behaviour. Code follows the specs; a behaviour change updates
the spec in the same pull request. They are written from phase 2 on.

| Spec | Covers | Phase |
|---|---|---|
| `workspace.md` | Project folder, manifest, file types, ids, references, `.primum` archive | 2 |
| `variables-and-scopes.md` | Constants, variables, scopes, export/import, settings | 2 |
| `expressions.md` | The small, safe expression language used in conditions | 4 |
| `events.md` | Event sources, debounce, schedules and time windows | 4 |
| `engine-semantics.md` | Sequences in time, automations, arbitration, re-trigger, exclusive groups | 4 |
| `safety.md` | Safe state, limits, panic, test mode, watchdog | 3 |
| `deployment-package.md` | Package format, hash, minimum runtime version, activation, rollback | 4 |
| `board-profiles.md` | Board profile format | 2 |
| `drivers.md` | Driver manifest: capabilities, config, platforms, safe state, conflict policy | 3 |
| `protocol.md` | Messages between boards and transports | after v1 |
