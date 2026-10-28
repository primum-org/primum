---
paths:
  - "packages/runtime/**"
---

# Runtime and safety rules

- Hardware is reached only through the HAL; every HAL has a simulated implementation.
- Every driver declares its safe state, its limits and its default conflict policy
  (exclusive for motors and servos, latest-wins for lights and relays). No exceptions.
- Safe state is applied on start, stop, crash (watchdog) and panic.
- Motors never reverse instantly: stop, wait the dead time, then change direction.
- Arbitration order: panic / safe state / driver limits → manual control and test mode →
  sequences by priority (latest command wins within the same priority).
- Test-mode commands expire on their own.
- Monotonic clock for durations; wall-clock only for schedules and only when reliable.
- Writable paths are configurable and default to `/data`. Only the hardware manager writes
  to `/boot/firmware`, and always through the tryboot flow.
- Tests that need a real board are marked `@pytest.mark.hw`.
