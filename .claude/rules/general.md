# General rules

- Small functions with descriptive names. No dead code, no commented-out code, no comments
  that repeat what the code says; comment the *why*.
- Errors carry a stable `code`, a clear message and a `hint`. They are shown to users and to AI.
- Prefer early returns over deep nesting; named constants over magic numbers.
- Never swallow an exception silently: handle it, or let it propagate with context.
- Do not widen a change beyond the task. Note follow-ups instead of doing them.
- New behaviour comes with tests. A bug fix comes with a test that reproduces the bug.
- User-visible text is never hard-coded in logic: it goes through i18n (English default, Spanish second).
