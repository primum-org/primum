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
- `gpiod` is a dependency of `primum-runtime` with the marker `sys_platform == 'linux'`. Its
  own type hints (`py.typed`) pass pyright strict, so no local stubs are needed.
- `gpiod` is imported only by `primum_runtime/hal/gpiod_hal.py`, and that module is imported
  lazily by `create_hal`. An import-linter contract forbids `gpiod` anywhere else in the runtime.
- HAL failures are `PrimumError`s with codes (`hal.pin_in_use`, `hal.pin_unavailable`,
  `hal.closed`), per decision 0009.

## Alternatives considered
- `gpiod` used directly in phase 1, HAL in phase 3: breaks the rule from the first commit and
  means rewriting phase 1 code.
- An optional extra (`primum-runtime[pi]`) with local type stubs: needed only if `gpiod` did
  not build or type-check on CI; it does both on `ubuntu-latest`.

## Consequences
- The simulated runtime works on any OS; real-hardware tests are marked `hw` and run on the Pi.
- Linux CI builds `gpiod` and type-checks the real HAL against its real types.
- On the Pi, `gpiod` must install from a wheel or build from source (checked in block 1.4).
- A released line may float, so phase 1 drives LEDs only, never relays.
