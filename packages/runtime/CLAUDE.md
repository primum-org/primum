# primum-runtime

The service that runs on Linux boards. It executes deployment packages from `primum-core`.

- Talks to hardware only through the HAL. Every HAL has a simulated implementation, and
  tests use it; tests that need a real board are marked `@pytest.mark.hw`.
- Safety first: every output has a safe state applied on start, stop, crash and panic.
- Measure durations with a monotonic clock. Wall-clock time only for schedules, and only
  when it is known to be reliable (the Pi 4 has no RTC).
- Writable paths are configurable and default to `/data` (the root filesystem becomes
  read-only in the Primum OS image).
- Only the hardware manager may write to `/boot/firmware`.
