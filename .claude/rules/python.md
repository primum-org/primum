---
paths:
  - "packages/**/*.py"
  - "tools/**/*.py"
---

# Python rules

- Python 3.13. Full type hints; pyright runs in strict mode. No `Any`, no `cast`, no
  `# type: ignore` without a comment explaining why.
- `pydantic` models at the edges (API, files, packages); `@dataclass(frozen=True)` or plain
  immutable values inside.
- Logging with `logging.getLogger(__name__)` and parameterised messages; never `print`.
- `pathlib.Path` for paths. No mutable default arguments. No module-level mutable state.
- Dependencies are added with `uv add <pkg> --package <member>`; never edit `uv.lock`.
