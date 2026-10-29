# Message catalogs

All user-visible text: `en.json` (default locale) and `es.json`. Errors are keyed by their code
(`pin.in_use`) with a `message` and a `hint` using `{param}` placeholders; UI strings will use
their own namespace. `core` returns codes and params, never text
([decision 0009](../docs/decisions/0009-error-codes-and-message-catalogs.md)). The catalogs and
the consistency test arrive with the first error, in phase 2.
