# primum-runtime

The service that runs on Linux boards. It executes deployment packages from `primum-core`.

- Talks to hardware only through the HAL (`primum_runtime.hal`, decision 0010): get one with
  `create_hal(simulate=...)` and keep it in a `with` block. Every HAL has a simulated
  implementation, and tests use it; tests that need a real board are marked `@pytest.mark.hw`.
- `gpiod` is imported only by `hal/gpiod_hal.py` (`just arch` enforces it).
- Layers: `cli` → `api` → `config` → `control` → `hal` → `errors`; each imports only the ones
  below it, and FastAPI, uvicorn and pydantic stay in `api` and `cli` (`just arch`, decision 0011).
  The API commands outputs through `control.Controller`, never through the HAL.
- API handlers are `async`: they all run on the event loop's thread, so `control` needs no locks.
- Never run `hw` tests or drive lines on a Pi that runs other GPIO software, such as the belén's
  Pi (`rpi4b`): the kernel does not see lines driven through `/dev/gpiomem` (decision 0010).
- Errors are `PrimumError(ErrorCode.X, params)` (decision 0009), never text. System text (for
  example `strerror`) goes in a `detail` param. A new code goes in `ErrorCode` and in both
  catalogs in `i18n/` (`test_catalogs.py` checks it).
- The page lives in `ui/` (no build step). `ui/generated/` holds copies of `i18n/` and `design/`
  assets made by `just gen`: never edit them, edit the source and regenerate. UI keys are written
  literally (`t("panic.button")`, `data-i18n="panic.button"`) so the catalog test finds them.
- Safety first: every output has a safe state applied on start, stop, crash and panic.
- Measure durations with a monotonic clock. Wall-clock time only for schedules, and only
  when it is known to be reliable (the Pi 4 has no RTC).
- Writable paths are configurable and default to `/data` (the root filesystem becomes
  read-only in the Primum OS image).
- Only the hardware manager may write to `/boot/firmware`.
