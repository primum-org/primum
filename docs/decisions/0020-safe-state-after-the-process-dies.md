# 0020. The runtime declares what it claims; `primum-safe` makes it safe after every stop

- Status: Accepted
- Date: 2026-11-17

## Context
The safe state was applied by the process that owned the outputs: on start, on panic and on a
stop it could handle. Measured on the Pi in block 1.4 and again in 3.1: after `SIGKILL` a
line keeps its last level and a PWM channel keeps running, until the service starts again and
claims them; if systemd gives up restarting, they stay so. A process that hangs without
dying was not covered at all.

The plan asked for a systemd watchdog and a unit run when the service fails
(`OnFailure=primum-safe.service`) that drives what the runtime declared in `/data`.

## Decision
- **The runtime declares what it claims before it claims it**: a file in its data directory
  with the board, the digital outputs (pin, `activeLow`) and the PWM outputs (pin, frequency).
  Written whole, flushed and renamed. A runtime that cannot declare does not claim. The
  declaration is removed after a clean stop.
- **`primum-safe` runs after every stop of the service** (`ExecStopPost=`), not only when
  systemd gives up: it runs before any restart, so the output is not left on for the seconds
  a restart takes, and it cannot race with the restarted service for the lines.
- **`primum-safe` is the HAL used once more**: it claims what was declared and closes. A
  claim starts every output in its safe state; closing reads each one back and releases it.
  A second command of the runtime's package, in Python, tested against the simulated HAL.
- **It never guesses.** Nothing declared: it does nothing. A declaration it cannot read: an
  error, and nothing is touched.
- **The watchdog is the event loop's**: under `Type=notify` the runtime says it is ready and
  then, from the loop the API runs on, that it is alive. A loop that is stuck is a dead
  service to systemd.

## Alternatives considered
- **`OnFailure=` only**: the output stays on between a crash and the restart, and a unit of
  its own would start while the service restarts.
- **A shell script with `gpioset` and writes to sysfs**: it would work with a broken Python
  environment, but repeat what the HAL knows (the chip by label, `activeLow`, the order a PWM
  channel takes its writes in, the polarity) and could only be tested on the board.
- **Driving every GPIO of the board when there is no declaration**: it covers a lost file by
  turning into outputs pins that may be inputs with something driving them.
- **Not declaring, and making safe whatever the configuration says**: the configuration may
  have changed since the process that died read it.
- **A schema in `schemas/` for the declaration**: it is a note between two commands of one
  version of the runtime, not a format people or other programs write.
- **A watchdog thread**: it would beat while the loop that commands the outputs is stuck.

## Consequences
- After `kill -9` of the service every digital output it had claimed is in its safe state
  before the service is back. PWM channels too, through the same HAL; the service offers
  them once this is checked on the board.
- The service writes to disk on every start and removes a file on every clean stop.
- What is not covered is said in `specs/safety.md`: power loss, the instant before
  `primum-safe` finishes, a broken installation.
- The systemd side (`Type=notify`, the watchdog, `ExecStopPost=`) cannot be tested off the
  board: its checks are a procedure in `specs/safety.md`.
