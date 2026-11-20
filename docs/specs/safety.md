# Safety

What Primum guarantees about its outputs when things go wrong, and how. Why: decisions 0006
(panic above everything), 0010 and 0015 (the HAL's safe state) and 0020 (after a crash). This
spec grows with block 3.4: test mode is not here yet.

## The safe state

Every output has a safe state: a digital output is *off* (inactive; `activeLow` only says
which electrical level that is), a PWM output is at 0 %, with normal polarity. A driver's
manifest names it as an action (`safeState`), and a test ties the two.

| When | Who applies it | How it is known to have worked |
|---|---|---|
| Start | The HAL, on claiming: every output is requested in its safe state | The claim fails otherwise |
| Panic | The HAL (`apply_safe_state`), for every output, even if some fail | Each output is read back; failures are raised together (`hal.safe_state_incomplete`, `hal.safe_state_unverified`) |
| Stop (`SIGINT`, `SIGTERM`) | The HAL, on closing, before it releases the lines | The same; the service's exit status says so |
| The process dies (`SIGKILL`, the watchdog, a crash) | `primum-safe`, run by systemd after the service stops, and again before it starts | The same HAL: read back, then released; its exit status says so |

Safety is best-effort across outputs: one that fails never stops the others.

## After the process dies

A process killed at once cannot do anything, and the kernel keeps its outputs as they were:
a line stays at its last level, a PWM channel keeps running. So:

1. **The runtime declares what it claims before it claims it**, in its data directory
   (`/data/claimed.json`; `--data-dir`, `PRIMUM_DATA_DIR`): the board's model, each digital
   output with its `activeLow` and each PWM output with its frequency. Inputs are not declared.
   The file is written whole, flushed to the card and renamed into place. A runtime that
   cannot write it does not claim anything (`safe.declaration_unwritable`).
2. **After a clean stop the declaration is removed**: every output read back safe and was
   released. If the stop left an output unsafe, it stays declared.
3. **systemd runs `primum-safe` after every stop of the service** (`ExecStopPost=`), whatever
   stopped it and before any restart. It reads the declaration and claims what it names with
   the same HAL (a claim starts every output in its safe state), then closes it (each output
   is read back and released) and removes the declaration.
4. **systemd runs `primum-safe` before every start too** (`ExecStartPre=`). The runtime
   replaces the declaration it finds with its own, and its configuration may name other pins
   by now: what an earlier runtime left declared (because `primum-safe` was killed with it,
   or failed) is made safe first. If it cannot be, the service does not start, and so does
   not forget it; systemd tries again at each restart.
5. **A claim that fails leaves nothing declared**: nothing was claimed, and a declaration
   naming a pin the board lacks would fail `primum-safe` at every stop for no reason.

| Case | What `primum-safe` does | Exit |
|---|---|---|
| Nothing declared (a clean stop, a first start) | Nothing | 0 |
| A declaration, and every output reads back safe | Releases them, removes the declaration | 0 |
| An output that does not read back safe, a line someone else holds, a pin the board lacks | Logs the error; the declaration stays | 1 |
| A declaration that cannot be read (`safe.declaration_invalid`) | Touches nothing: it never guesses which pins were outputs | 1 |

A simulated service (`--simulate`) has no real outputs: it declares nothing.

Before a start, after `primum-safe`, the unit also refuses a board where a PWM channel is
still exported (`check-gpio-users.sh --pwm`): a channel has no owner, so the HAL would adopt
one that another program is using, or one `primum-safe` could not make safe.

The declaration is the runtime's own note to `primum-safe`, of the same version of Primum: it
is not a file format of a project, has no schema in `schemas/` and may change with the code
that writes and reads it.

## The watchdog

The unit is `Type=notify` with `WatchdogSec=10`. The runtime tells systemd `READY=1` once the
HAL is claimed and the API is about to serve, then `WATCHDOG=1` twice in every period systemd
allows (every 5 s), from the event loop the API runs on, and `STOPPING=1` when it shuts down.
A loop that is stuck stops the beats: systemd kills the service (a failure), `primum-safe`
runs, and the service is restarted (`Restart=on-failure`).

Outside systemd (a laptop, the tests) there is no socket to tell: nothing is sent.

## Checked on the board

The `hw` tests (`test_safe_hw.py`, `uv run just pi-test`) kill a process that holds an output
on and check that `primum-safe` turns it off: a digital output, and a PWM output when
`PRIMUM_HW_PWM_PIN` is set.

With the service itself, the LED on, as witness (`ssh primum-dev`):

| Do | Expect |
|---|---|
| `sudo systemctl kill -s KILL --kill-whom=main primum` | The LED goes off at once; `journalctl -u primum` shows `primum-safe` naming its GPIO; the service is back within seconds, the LED off |
| `sudo systemctl kill -s KILL primum` (the whole control group, `primum-safe` included) | `primum-safe` is killed as it starts, so the LED stays on until the restart, some 5 s; then `primum-safe` runs before the start and turns it off |
| The same, after changing `PRIMUM_PIN` to another GPIO with the LED on | The LED on the old GPIO goes off at the restart all the same: it was declared, and is made safe before the new declaration replaces it |
| `sudo systemctl kill -s STOP --kill-whom=main primum` (a stuck process) | Within 10 s the watchdog kills it; the LED goes off; the service is back |
| `sudo systemctl stop primum` | The LED goes off; `primum-safe` logs that nothing is declared |
| A pin the board lacks in `/etc/primum/runtime.env`, with the LED on before | The LED goes off with the stop; the service fails to start and systemd restarts it every 6 s or so, for as long as it takes (it does not give up: with `RestartSec=2` and a start of some 3 s the limit of restarts is never reached); `primum-safe` logs that nothing is declared each time |

Seen on `primum-dev` (Raspberry Pi 4, kernel 6.18): `READY=1` reaches systemd from uvicorn's
lifespan, `ExecStopPost=` runs after the watchdog kills the service, and `primum-safe` takes
about 0.34 s. The first run of this procedure found what rows 2, 3 and 6 say; with the fixes
for them, the whole procedure and the `hw` tests pass, as the owner of the board reports.

## Not covered

- Power loss and reboot: the lines go to their state at power on (their `defaultPull` in the
  board profile), not to a state Primum chose. Safe levels at boot are the hardware manager's
  (phase 6, `config.txt`).
- The moment between the process dying and `primum-safe` finishing: about a third of a
  second on a Raspberry Pi 4 (it starts Python); the seconds until the restart when
  `primum-safe` is killed together with the service. An output that must never stay on that long needs
  hardware that fails safe on its own.
- A broken installation: `primum-safe` runs from the same environment as the service.
- A service started by hand, without systemd: nothing runs `primum-safe` for it.
