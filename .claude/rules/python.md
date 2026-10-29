---
paths:
  - "packages/**/*.py"
  - "tools/**/*.py"
---

# Python rules

- Python 3.13. Full type hints; pyright runs in strict mode. No `Any`, no `cast`, no
  `# type: ignore` without a comment explaining why.
- Formats come from the JSON Schemas in `schemas/` (decision 0008): `core` uses the generated
  frozen dataclasses and validates structure with `fastjsonschema`. pydantic is allowed only at
  the runtime's edges (HTTP API), never in `core`. Inside: `@dataclass(frozen=True)` or plain
  immutable values.
- Outside `core`: logging with `logging.getLogger(__name__)` and parameterised messages, and
  `pathlib.Path` for filesystem paths. Inside `core`: no logging (diagnostics are returned as
  values) and `PurePosixPath` only (see `core.md`). Never `print`.
- No mutable default arguments. No module-level mutable state.
- Dependencies are added with `uv add <pkg> --package <member>`; never edit `uv.lock`.
