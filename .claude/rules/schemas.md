---
paths:
  - "schemas/**"
  - "boards/**"
---

# Schema and board profile rules

- `schemas/` holds hand-written JSON Schemas (draft 2020-12): the single source of every file
  format (decision 0008). Python dataclasses, TypeScript types and reference docs are generated.
- Every format has a `schemaVersion`. A breaking change bumps it and ships a migration from the
  previous version, with a test that loads a file of the previous version.
- Every entity has a UUID `id`. References use ids.
- After changing a schema or a board profile, regenerate what depends on it; never edit
  generated files.
