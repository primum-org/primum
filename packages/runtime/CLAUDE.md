# primum-runtime

The service that runs on Linux boards. It executes deployment packages from `primum-core`.

- Talks to hardware only through the HAL (`primum_runtime.hal`, decision 0010): get one with
  `create_hal(simulate=..., board=...)` and keep it in a `with` block. A HAL drives one board
  (`board.load_board("rpi4b")`, from the profiles of `boards/`): it only hands out the GPIOs
  the profile lists, simulated or not. Everything is claimed at once (`hal.claim(Claim(...))`,
  decision 0015): one request per chip, inputs with edge events, PWM through sysfs. Every HAL
  has a simulated implementation, and tests use it; tests that need a real board are marked
  `@pytest.mark.hw`.
- `gpiod` is imported only by `hal/gpiod_hal.py` (`just arch` enforces it).
- The service runs a deployment package (`--package`, decision 0025): `package.load_package`
  reads it with `core` and checks it against the drivers and the board before anything is
  claimed, and refuses it whole. A package is never trusted for having a right hash. Elements
  are asked for by their id (`ElementConfig.key`), never by their name.
- The controller is the arbiter of every output (decision 0026): panic, then what a person
  asked (manual control or a test), then the sequences, as `engine.Engine` says. The engine
  touches no hardware and reads no clock; a test holds it to `core`'s oracle. Nothing writes
  an output but `Controller._settle` and a person's command.
- Elements are driven through drivers (`primum_runtime.drivers`, decision 0019): one per
  element type, made from the element, its manifest (`drivers/`) and the limits of its board.
  The HAL's specs have no defaults: a driver gives every option. A new driver comes with its
  manifest and its tests against the simulated HAL.
- Layers: `cli` and `safe` → `api` → `config` → `package` → `board` → `control` → `engine` → `drivers` →
  `declared` → `hal` → `systemd` → `errors`; each imports only
  the ones below it, and FastAPI, uvicorn and pydantic stay in `api` and `cli` (`just arch`,
  decision 0011).
  The API commands outputs through `control.Controller`, never through the HAL or a driver.
- API handlers are `async`: they all run on the event loop's thread, so `control` needs no locks.
- Never run `hw` tests or drive lines on a Pi that runs other GPIO software: the kernel does not
  see lines driven through `/dev/gpiomem`, so a "free" pin may have a relay on it (decision 0010).
- Errors are `PrimumError(ErrorCode.X, params)` (decision 0009), never text. System text (for
  example `strerror`) goes in a `detail` param. A new code goes in `ErrorCode` and in both
  catalogs in `i18n/` (`test_catalogs.py` checks it).
- The page lives in `ui/` (no build step). `ui/generated/` holds copies of `i18n/` and `design/`
  assets, and `generated/boards/` and `generated/drivers/` copies of the board profiles and the
  driver manifests, made by `just gen`: never edit
  them, edit the source and regenerate. UI keys are written literally (`t("panic.button")`,
  `data-i18n="panic.button"`) so the catalog test finds them.
- Safety first: every output has a safe state applied on start, stop, crash and panic. A
  crash is covered from outside the process (decision 0020, `docs/specs/safety.md`): the
  service declares what it claims in its data directory before claiming it
  (`primum_runtime.declared`), and systemd runs `primum-safe` (`primum_runtime.safe`) after
  every stop. Anything new that the service claims must be declared.
- Measure durations with a monotonic clock. Wall-clock time only for schedules, and only
  when it is known to be reliable (the Pi 4 has no RTC).
- Writable paths are configurable and default to `/data` (the root filesystem becomes
  read-only in the Primum OS image).
- Only the hardware manager may write to `/boot/firmware`. The one exception, until it exists,
  is `enable_pwm` in `image/provision.sh` for the development Pi: not a precedent.
