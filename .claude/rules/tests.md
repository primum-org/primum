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
  block 1.4, `just pi-test` will sync the code to the development Pi and run them there).
- Prefer small, explicit fixtures over large shared ones.
