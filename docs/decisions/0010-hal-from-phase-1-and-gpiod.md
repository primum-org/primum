# 0010. The HAL exists from phase 1; gpiod is a Linux-only dependency behind it

- Status: Accepted
- Date: 2026-10-29

## Context
The runtime rules say hardware is reached only through the HAL, with a simulated
implementation, but the plan put the HAL in phase 3 while phase 1 already drives a GPIO line.
`gpiod` (libgpiod v2 bindings) compiles a C extension, does not exist on macOS or Windows, and
had to pass pyright in strict mode.

## Decision
- A minimal HAL lands in phase 1 (`primum_runtime.hal`): `Hal`, `DigitalOutput`,
  `OutputSpec`, a `SimulatedHal` and a `GpiodHal`, chosen by `create_hal(simulate=...)`.
  Phase 3 extends it (inputs, PWM, crash safety) instead of introducing it.
- The safe state of a digital output is *off*. It applies when the output is created, on
  `apply_safe_state` and on `close`, including when leaving a `with` block on an exception.
- Safety is best-effort across outputs: if one line fails, the others are still put in the
  safe state and released, and the failures are raised together at the end.
- `gpiod` is a dependency of `primum-runtime` with the marker `sys_platform == 'linux'`. Its
  own type hints (`py.typed`) pass pyright strict, so no local stubs are needed.
- `gpiod` is imported only by `primum_runtime/hal/gpiod_hal.py`, and that module is imported
  lazily by `create_hal`. An import-linter contract forbids `gpiod` anywhere else in the runtime.
- HAL failures are `PrimumError`s with codes (`hal.pin_in_use`, `hal.pin_unavailable`,
  `hal.closed`, `hal.safe_state_incomplete`, `hal.release_incomplete`, and `hal.pin_invalid`
  for an offset the chip does not have, which gpiod reports as `ValueError`), per decision 0009.
  No raw exception from gpiod leaves the HAL.
  System text such as `strerror` goes in a `detail` parameter, shown as a technical detail.

## Alternatives considered
- `gpiod` used directly in phase 1, HAL in phase 3: breaks the rule from the first commit and
  means rewriting phase 1 code.
- An optional extra (`primum-runtime[pi]`) with local type stubs: needed only if `gpiod` did
  not build or type-check on CI; it does both on `ubuntu-latest`.

## Consequences
- The simulated runtime works on any OS; real-hardware tests are marked `hw` and run on the Pi.
- Linux CI builds `gpiod` and type-checks the real HAL against its real types.
- On the Pi, `gpiod` must install from a wheel or build from source with its bundled libgpiod
  (checked first thing in block 1.4).
- What happens to a released line depends on the kernel and the board. On the development
  Pi 4 (checked on 2026-10-30), a released line stays an output with no consumer and keeps
  its last value, so after `close()` it stays driven low; it does not float. That is not a
  guarantee across kernels or boards, so phase 1 drives LEDs only, never relays: relays wait
  for safe boot levels in `config.txt` (phase 6) and the watchdog (phase 3).
- Known limit: a second Ctrl+C while the HAL is closing interrupts it (only `Exception` is
  collected), and lines may stay active. Acceptable with LEDs only; the watchdog of phase 3
  covers crashes.
- `GpiodHal` requests one line per output. When the per-board arbiter arrives (phase 3), one
  request per chip is likely better.
- Line offsets equal BCM numbers on a Pi 4 with `/dev/gpiochip0`. On a Pi 5 the chip and the
  numbering depend on the kernel: they must come from the board profile, not from constants.
