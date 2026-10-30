---
paths:
  - "packages/runtime/**"
---

# Runtime and safety rules

- Hardware is reached only through the HAL; every HAL has a simulated implementation.
- Every driver declares its safe state, its limits and its default conflict policy
  (exclusive for motors and servos, latest-wins for lights and relays). No exceptions.
- Safe state is applied on start, stop, crash (watchdog) and panic, best-effort across
  outputs: one failing line never stops the others; failures are raised together at the end.
  "Stop" means the process closes the HAL: `SIGINT` does it through the `with` block, `SIGTERM`
  only once the service handles it (phase 1.2, uvicorn's lifespan), and `SIGKILL` never; what
  the process cannot do is covered by the watchdog (phase 3) and safe boot levels (phase 6).
- Motors never reverse instantly: stop, wait the dead time, then change direction.
- Arbitration order: panic / safe state / driver limits → manual control and test mode →
  sequences by priority (latest command wins within the same priority).
- Test-mode commands expire on their own.
- Monotonic clock for durations; wall-clock only for schedules and only when reliable.
- Writable paths are configurable and default to `/data`. Only the hardware manager writes
  to `/boot/firmware`, and always through the tryboot flow.
- Tests that need a real board are marked `@pytest.mark.hw` (`just test-hw` on the Pi).
