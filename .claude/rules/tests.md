---
paths:
  - "packages/*/tests/**"
---

# Test rules

- pytest. Arrange, act, assert. One behaviour per test, named after it
  (`test_<what>_<when>_<expected>`).
- Deterministic: no real sleeps, no wall clock, no network. Inject a fake clock.
- Hardware through the simulated HAL. Tests that need a real board are marked
  `@pytest.mark.hw` and run with `just pi-test`.
- Prefer small, explicit fixtures over large shared ones.
