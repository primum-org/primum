# Schemas

Hand-written JSON Schemas (draft 2020-12,
[decision 0008](../docs/decisions/0008-json-schema-as-the-source-of-formats.md)) of every file
format: project manifest, `.sec`, `.auto`, `.evt`, `.sched`, `.vars`, `.hw`, deployment
package, board profiles and driver manifests. They are the single source: `uv run just gen`
generates from them, into `packages/core/src/primum_core/generated/`, the schemas `core`
validates against and a frozen dataclass, with its parser, for every object
(`tools/gen_schemas.py`, [decision 0014](../docs/decisions/0014-generating-core-types-from-the-schemas.md)).
TypeScript types follow in phase 5.

| Schema | Format |
|---|---|
| `common.schema.json` | Definitions shared by every format: `id`, `name`, `description` |
| `project.schema.json` | `project.json`, the manifest at the root of a project |

## The subset of JSON Schema we use

Small on purpose: every format must map to plain types in Python, TypeScript and, later, C++.
The generator fails on anything outside it.

- Keywords: `$schema`, `$id`, `$defs`, `$ref`, `$comment`, `title`, `description`, `examples`,
  `type` (a single type), `properties`, `required`, `additionalProperties`, `items`, `enum`
  (all strings or all integers), `const`, `default` (optional scalars only), `format` (only
  `uuid`), `pattern`, `minLength`, `maxLength`, `minimum`, `maximum`, `minItems`, `maxItems`,
  `uniqueItems`.
- A file's `$id` is its file name; schemas refer to each other by it
  (`common.schema.json#/$defs/id`). `$ref` points at a whole schema or at one of its `$defs`.
- Every object sets `additionalProperties: false` (a misspelled field is reported, not
  ignored) and is either a whole schema (its class is named after `title`) or one of its
  `$defs` (named after its key). Objects are never written inline inside another.
- Property names are camelCase (`schemaVersion`); the Python fields are snake_case
  (`schema_version`).
- Every file format has `id` (a UUID), a `kind` const and a `schemaVersion` const, all
  required.

## Versions

Until the first release, formats are drafts: `schemaVersion` stays `1` and a format may change
without a migration, because no user files exist yet. From the first release on, a breaking
change bumps `schemaVersion` and ships a migration from the previous version, with a test that
loads a file of that version.
