# 0033. A package is stored, then activated; the one before is kept to be put back

- Status: Accepted
- Date: 2026-11-23

## Context
A package got to a board by hand: copied to the Pi, named in the service's configuration,
the service restarted. A package the board could not run kept the service from starting, and
systemd restarting it for ever. Phase 4 is done when a package is deployed, runs, and can be
rolled back. The API has no pairing yet (the PIN is phase 5), and an invariant of the
project is that nothing moves hardware without a person confirming it.

## Decision
- **Two steps: store, then activate.** `PUT /api/package` checks a package against the
  board and keeps it; nothing that runs changes. `POST /api/package/activate` names a kept
  package by its hash and runs it. No single request, and no upload by mistake, changes what
  a board does.
- **A service told neither a package file nor pins runs what was activated on it.** That is
  how a board is meant to run. `--package` and `--pin` stay, for development: such a
  service runs that and takes no packages (`package.fixed`).
- **Three packages at most are kept**, in `packages/` under the data directory, each named
  by its hash: the active one, the previous one, and the one stored and not activated yet.
  A state file says which is which, written whole and renamed into place.
- **Activating stops everything and starts from nothing.** What runs is closed: sequences
  stop, what is pending of the variables is written, every output goes to its safe state
  and the HAL is let go of. Then the new package opens a HAL of its own and claims its
  elements. Nothing carries over but the persistent variables and the trace.
- **The board writes which package is active before it touches what runs.** A card that
  went read-only refuses the activation with nothing changed, instead of leaving a package
  running that a restart would not bring back.
- **A package that cannot be started is not activated**: what ran before is started again
  and stays the active one (`package.activation_failed`). A board is not left running
  nothing because a package would not go.
- **What runs failing to stop is told apart** (`package.stop_failed`): it is not the
  package's doing, and the outputs are not known to be safe. What ran is claimed again,
  which puts them in their safe state.
- **Not while panic is on**: panic is released by a person, not by a package. It is looked
  at for the last time where nothing is awaited any more before the package runs: a new
  controller is born without panic, so a panic that came in between would be taken away.
- **Putting the previous one back is activating it**: the two swap, so it can be undone.
- **Persistent variables are the project's, not the package's** (decision 0031): a package
  put back finds the values there are now, if it still takes them. A counter does not go
  back because the lights did.
- **A service with nothing it can run starts empty and says why**: no package activated
  yet, or the active one no longer reads, no longer fits or cannot be claimed. The API is
  there to give it another.
- **Checking a package is off the event loop**, when it is stored and when it is
  activated: it takes time in proportion to the package, and panic must never wait behind
  it. What the packages are is told from the state file, never by reading them.
- **The trace goes on through an activation** (`package.stored`, `package.activated`,
  `package.refused`), with the same numbers and the same id.

## Alternatives considered
- **One request that stores and activates**: one call from anything on the network changes
  what a board does. Two steps are not a lock, but they are a decision.
- **Wait for the PIN of phase 5 before any route**: the phase would not be done, and the
  logic is the same with or without it. Noted as the first thing the PIN must cover.
- **Restart the process to activate**: simplest, and systemd already makes the outputs safe
  after a stop. But the API goes away for seconds, the trace is lost, and a package that
  does not start leaves the board down instead of on the one before.
- **Keep the claim and swap only what differs**: no blink of the outputs that both
  packages share. And a state nobody can reason about: a new package must start from the
  safe state, as a service does.
- **Try the previous package when the active one cannot be run at start**: it would run,
  unasked, something a person replaced on purpose.
- **Keep the values of the variables with each package and restore them on rollback**: it
  undoes the counters with the lights. What was dropped is still set aside (`.bak`).
- **A history of every package**: more to keep whole on a card; "the one before" is what
  undoing needs.

## Consequences
- The data directory has `packages/` now. A board runs with `PRIMUM_PIN` and
  `PRIMUM_PACKAGE` both unset.
- Activating blinks every output through its safe state, also the ones both packages have.
- Until the PIN exists, whoever reaches the API on the network can store and activate a
  package. The service listens on `127.0.0.1` unless it is told otherwise.
- A service started with `--package` and a file it cannot run still does not start, and
  systemd still restarts it: that option is for development now.
- The controller is made again at each activation: nothing may keep one across requests.
  The trace and the broadcaster of states are the service's, and stay.
- Reopening the HAL in one process (close, then open and claim again) is what activation
  relies on. It is tested on the simulated HAL only.
