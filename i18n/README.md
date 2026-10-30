# Message catalogs

All user-visible text: `en.json` (default locale) and `es.json`
([decision 0009](../docs/decisions/0009-error-codes-and-message-catalogs.md)).

- `errors`: one entry per error code (`hal.pin_in_use`), with a `message` and a `hint` that
  use `{param}` placeholders. The runtime and `core` return codes and params, never text.
- `ui`: the strings of the runtime's page, by key (`panic.button`).

Rules, checked by `packages/runtime/tests/test_catalogs.py`:

- Both catalogs have the same keys, and each string the same placeholders.
- Every code in `primum_runtime.errors.ErrorCode` has an entry, and every entry is a code.
- Every `ui` key the page uses exists, and every `ui` key is used.
- Placeholders name params the error always carries. Params named `detail`, `consumer` and
  `fields` are technical text: the page shows them apart, never inside the message. Tuple
  params (lists of pins) are formatted for the language ("17 and 27", "17 y 27").

After editing a catalog, run `uv run just gen`: the runtime serves a generated copy.
