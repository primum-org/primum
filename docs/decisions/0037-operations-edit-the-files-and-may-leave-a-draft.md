# 0037. An operation edits the project's files, and may leave a project with problems

- Status: Accepted
- Date: 2026-11-27

## Context
Block 5.4 brings editing: until now `core` only read a project. The architecture already
says that every edit is an operation of `core` (project in, project or errors out), used
alike by the web UI, Primum Studio and the MCP server. What was open: what "a project" is to
an operation, how an operation is written, whether the result must be a valid project, and
where the `.primum` file (the zip of a project, `specs/workspace.md`) is read and written.

## Decision
- **A project is its files** (path → bytes), the same thing `load_workspace` takes. An
  operation gives back the files, one of them new. Nothing else has to be kept in step: the
  files are what is stored, sent and validated.
- **An operation is data**, with its schema (`schemas/operation.schema.json`): one object
  with an `op` and the fields of that `op`, like the other formats with cases (an event, an
  automation's action). What goes with each `op` is checked by `core`. It names things by
  id, never by path.
- **The changed file is edited as the JSON document it is**, not through the generated
  dataclasses, which only read. It is written again whole, in one style.
- **A project may be left with problems.** An operation is refused only if it is malformed,
  names something that is not there, or would give the file it changes a problem of its own
  that it did not have. What it means for the rest of the project is listed by
  `load_workspace`, and only building a package requires a valid project.
- **The `.primum` file is read and written in `core`** (`primum_core.archive`), in memory.
  `just arch` forbids `io` in `core` because it is how files and streams are reached; this
  one module may import it, for `BytesIO` alone. Bytes in, bytes out, with fixed dates: it
  stays pure and deterministic. Reading has limits (2000 files, 64 MB unpacked) and refuses
  paths that leave the folder, links, and names two systems would read differently.

## Alternatives considered
- Operations over the typed model, with a writer generated from the schemas: more code to
  generate and keep, for the same files; worth it if operations grow complex.
- One schema per operation: clearer types, but the subset of JSON Schema we allow has no
  `oneOf`, and the generator would need it.
- Every operation must leave a valid project: simple to explain, but an element could not be
  added before its pin is chosen, and a project uploaded with a problem could not be fixed
  on the board.
- The `.primum` file in the runtime: the CLI and Primum Studio would need it again, and the
  runtime and the CLI may not import each other. A package of its own for a hundred lines.

## Consequences
- Whoever stores a project must be ready for an invalid one, and show its problems.
- A partial fix of a problem a file already had can be refused, because the problem changes
  and so counts as new: it is fixed in one operation.
- Formatting by hand is lost at the first operation on a file.
- The exception for `io` is one line in `pyproject.toml`; a second module asking for it
  should be a new decision, not a longer list.
