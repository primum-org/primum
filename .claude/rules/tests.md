---
paths:
  - "packages/*/tests/**"
  - "tools/tests/**"
---

# Test rules

- pytest. Arrange, act, assert. One behaviour per test, named after it
  (`test_<what>_<when>_<expected>`).
- Deterministic: no real sleeps, no wall clock, no network. Inject a fake clock.
- Hardware through the simulated HAL. Tests that need a real board are marked
  `@pytest.mark.hw`: `just test` skips them; on the Pi they run with `just test-hw` (from
  phase 1, `just pi-test` syncs the code to the development Pi and runs them there).
- Prefer small, explicit fixtures over large shared ones.
