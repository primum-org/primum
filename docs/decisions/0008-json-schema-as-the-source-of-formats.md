# 0008. Hand-written JSON Schema is the source of every file format

- Status: Accepted
- Date: 2026-10-29

## Context
The formats (project files, deployment package, board profiles, driver manifests) are read and
written by `primum-core` (Python), the web UI and Primum Studio (TypeScript), later by
microcontroller firmware (C++) and maybe by a `core` rewritten in Rust. The plan said
"pydantic → JSON Schema", which contradicts the invariant that `schemas/` is the single
source, and pydantic (with its compiled Rust extension) is neither small nor easy to carry
into another language.

## Decision
- Every format is a **hand-written JSON Schema** (draft 2020-12) in `schemas/`. It is the source.
- Generated from it, never edited by hand:
  - Python: frozen dataclasses used by `primum-core` (generator chosen in phase 2, for example
    `datamodel-code-generator` with dataclass output);
  - TypeScript types for the web UI and Primum Studio (phase 5, for example
    `json-schema-to-typescript`);
  - the reference docs in `docs/reference/`.
- Structural validation inside `core` uses **`fastjsonschema`** (pure Python, no dependencies)
  against the same schemas. Meaning (scopes, references, pin conflicts) is validated by `core`
  code, because a schema cannot express it.
- pydantic may be used at the edges of the runtime (HTTP API), never in `core` and never as the
  source of a format.

## Alternatives considered
- **pydantic as the source**, exporting JSON Schema: faster to write and good error messages,
  but `core` would depend on a large compiled library, the real source would be Python, and a
  Rust or C++ implementation would have to re-model everything.

## Consequences
- `primum-core` gains one small, pure dependency (`fastjsonschema`) in phase 2.
- Schemas are more verbose to write; reviews of format changes happen on the schema.
- `just gen` grows to generate the Python and TypeScript types; `just check` fails if they are
  out of date, as it already does for the design tokens.
- Validation errors from the schema are mapped to error codes (decision 0009).
