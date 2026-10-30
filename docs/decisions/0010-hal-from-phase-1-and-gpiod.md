# 0010. The HAL exists from phase 1; gpiod is a Linux-only dependency behind it

- Status: Accepted
- Date: 2026-10-29

## Context
The runtime rules say hardware is reached only through the HAL, with a simulated
implementation, but the plan put the HAL in phase 3 while phase 1 already drives a GPIO line.
`gpiod` (libgpiod v2 bindings) is a C extension (a wheel where one exists, built from source
elsewhere), does not exist on macOS or Windows, and
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
- `GpiodHal` opens the chip when it is created and checks each pin before requesting it:
  against the chip's number of lines, and whether another consumer already holds the line.
  gpiod uses `ValueError` both for an offset out of range and for some lines the kernel owns
  (`ValueError(22, 'Invalid argument')` for GPIO 2 with I2C on), so errors are not told apart
  by exception type: after the checks, anything `request_lines` raises means unavailable.
- HAL failures are `PrimumError`s with codes, per decision 0009:
  - `hal.pin_invalid`: a negative pin (`OutputSpec`) or one the chip does not have (`lines`);
  - `hal.pin_in_use`: already claimed through this HAL;
  - `hal.pin_unavailable`: held by another consumer (`consumer`) or refused by the kernel
    (`detail`);
  - `hal.chip_unavailable` and `hal.chip_access_denied` (fix: the user joins group `gpio`),
    when `GpiodHal` is created;
  - `hal.unsupported_platform`: the GPIO HAL asked for where `gpiod` is not installed;
  - `hal.closed`, `hal.safe_state_incomplete`, `hal.release_incomplete`.

  No raw exception from gpiod leaves the HAL.
  System text such as `strerror` goes in a `detail` parameter, shown as a technical detail.

## Alternatives considered
- `gpiod` used directly in phase 1, HAL in phase 3: breaks the rule from the first commit and
  means rewriting phase 1 code.
- An optional extra (`primum-runtime[pi]`) with local type stubs: needed only if `gpiod` did
  not build or type-check on CI; it does both on `ubuntu-latest`.

## Consequences
- The simulated runtime works on any OS; real-hardware tests are marked `hw` and run on the Pi.
- Linux CI installs the `gpiod` wheel and type-checks the real HAL against its real types.
- On the Pi, `gpiod` must install from a wheel or build from source with its bundled libgpiod
  (checked first thing in block 1.4).
- The kernel only knows lines requested through the character device. Software that writes
  `/dev/gpiomem` directly (RPi.GPIO, pigpio) drives lines the kernel reports as free, so
  `hal.pin_in_use` and `hal.pin_unavailable` cannot see it. Primum never shares a Pi with
  other GPIO software; provisioning (block 1.4) refuses to run where it finds some.
- What happens to a released line depends on the kernel and the board. On a Pi 4 (checked on
  2026-10-30, the belén's Pi, not a Primum development Pi), a released line stays an output with no consumer and keeps
  its last value, so after `close()` it stays driven low; it does not float. That is not a
  guarantee across kernels or boards, so phase 1 drives LEDs only, never relays: relays wait
  for safe boot levels in `config.txt` (phase 6) and the watchdog (phase 3).
- Known limit: a second Ctrl+C while the HAL is closing interrupts it (only `Exception` is
  collected), and lines may stay active. Acceptable with LEDs only; the watchdog of phase 3
  covers crashes.
- Known limit: the safe state on stop needs the process to close the HAL. Measured on the
  same Pi 4 (2026-10-30) on GPIO 17, with nothing wired to it, by reading the line after
  driving it active: after `SIGINT` it is low; after `SIGTERM` and `SIGKILL` it stays high, because Python dies without running `__exit__`. Phase 1.2 fixes
  `SIGTERM` (uvicorn runs the lifespan shutdown) and tests it by killing a real process;
  `SIGKILL` cannot be handled, so it is left to the watchdog (phase 3) and safe boot levels
  (phase 6).
- The simulated HAL accepts any non-negative pin, so `--simulate` can accept a pin the board
  does not have. It checks pins against the board profile from phase 2.
- `GpiodHal` requests one line per output. When the per-board arbiter arrives (phase 3), one
  request per chip is likely better.
- Line offsets equal BCM numbers on a Pi 4 with `/dev/gpiochip0`. On a Pi 5 the chip and the
  numbering depend on the kernel: they must come from the board profile, not from constants.
