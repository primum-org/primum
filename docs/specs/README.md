# Specifications

Exact, testable descriptions of behaviour. Code follows the specs; a behaviour change updates
the spec in the same pull request. They are written from phase 2 on.

| Spec | Covers | Phase |
|---|---|---|
| [`workspace.md`](workspace.md) | Project folder, manifest, file types, ids, references, `.primum` archive; what a clip does and who commands an element | 2 |
| [`variables-and-scopes.md`](variables-and-scopes.md) | Constants, variables, scopes, export/import, settings, components | 2 |
| [`expressions.md`](expressions.md) | The small, safe expression language used in conditions: what can be written, its types, its compiled form in the package, how it is evaluated | 4 |
| [`events.md`](events.md) | Events and what makes them happen, automations: several on one event, actions, increments, failures, panic; later schedules and time windows | 4 |
| [`trace.md`](trace.md) | What the board did and why: the entries, their kinds, how many are kept, the API | 4 |
| [`engine-semantics.md`](engine-semantics.md) | Which sequences are running: starting, stopping, re-trigger, exclusive groups, restarts; later automations and arbitration | 4 |
| [`safety.md`](safety.md) | Safe state, panic, the watchdog and `primum-safe` after a crash, test mode | 3 |
| [`deployment-package.md`](deployment-package.md) | Package format, its commands and its hash, `primum build`; later activation and rollback | 4 |
| [`board-profiles.md`](board-profiles.md) | Board profile format, rules and use | 2 |
| [`drivers.md`](drivers.md) | Driver manifest: actions, config, safe state, conflict policy; what `core` checks against it; the drivers of the runtime | 3 |
| `protocol.md` | Messages between boards and transports | after v1 |
