# 0009. Errors are codes with parameters; text lives in translation catalogs

- Status: Accepted
- Date: 2026-10-29

## Context
Errors from `core` must be clear for users and useful for AI assistants, but no user-visible
text may be hard-coded: the UI is in English and Spanish. Writing messages inside `core` would
also tie it to one language and make the MCP server and the UI disagree.

## Decision
- An error returned by `core` carries **no text**, only:
  - `code`: stable, dotted, `<area>.<reason>` (for example `pin.in_use`);
  - `params`: simple values (strings, numbers, booleans, ids) used by the message
    (for example `{"pin": 18, "element": "LED strip", "suggestion": 23}`);
  - `location`: the file id and a JSON Pointer inside it, when it applies.
- All user-visible text lives in **message catalogs** in `i18n/`: `en.json` (default) and
  `es.json`. Error entries are keyed by code and hold a `message` and a `hint`, with `{param}`
  placeholders. UI strings will live in the same catalogs under their own namespace.
- The web UI and Primum Studio render the text in the user's language. The MCP server and the
  CLI render English text plus the hint, so AI assistants get the same guidance.
- A test checks that **every code `core` can return has an entry, with the same placeholders,
  in every catalog**, and that catalogs contain no unused codes.
- Codes are part of the public contract: renaming one is a breaking change.

## Alternatives considered
- English messages in `core` translated later: two sources of truth for the same text, and a
  rewrite of every error when the UI is translated.
- gettext with English strings as keys: changing the English wording would break the Spanish
  translation and the AI-facing contract.

## Consequences
- `core` stays language-independent and testable by comparing codes and params.
- Adding an error means adding its code, its catalog entries in both languages and a test.
- Schema validation errors (decision 0008) are mapped to codes as well.
