# General rules

- Small functions with descriptive names. No dead code, no commented-out code, no comments
  that repeat what the code says; comment the *why*.
- Errors carry a stable `code` (`<area>.<reason>`), `params` and, when it applies, a `location`;
  never text. Their message and hint live in the catalogs in `i18n/` (decision 0009). Users and
  AI read them.
- Prefer early returns over deep nesting; named constants over magic numbers.
- Never swallow an exception silently: handle it, or let it propagate with context.
- Do not widen a change beyond the task. Note follow-ups instead of doing them.
- New behaviour comes with tests. A bug fix comes with a test that reproduces the bug.
- User-visible text is never hard-coded: it lives in `i18n/en.json` (default) and `i18n/es.json`.
