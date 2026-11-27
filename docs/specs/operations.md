# Operations: editing a project

Every edit of a project is an operation: a small JSON document that says what to change.
`core` applies it (`primum_core.operations.apply_operation`): the project's files and the
operation in, the files with the change, or the issues that refuse it, out. The web UI, the
MCP server and Primum Studio send the same operations; none of them edits a file itself
(decision 0037). The format is `schemas/operation.schema.json`.

A project is its files, as `load_workspace` takes them (`workspace.md`): path → content. The
files given are never changed; the ones that come back are the same objects, except the one
the operation changed.

## The operations there are

| `op` | Changes | Names it by | May set | May clear |
|---|---|---|---|---|
| `set_project` | the manifest, `project.json` | nothing: a project has one | `name`, `description`, `timeZone` | `description`, `timeZone` |
| `set_variable` | one variable of a `.vars` file | `variable`, its id | `label`, `initial`, `min`, `max`, `step`, `persistent`, `setting` | `label`, `min`, `max`, `step` |

```json
{ "op": "set_variable", "variable": "334b5eab-ff76-40b9-aafe-c7155710ff8e",
  "label": "Brightness", "max": 100, "step": 5, "clear": ["min"] }
```

- A field that is not given is left as it is. `clear` lists optional fields to take away.
- An operation is whole: it is applied with everything it says, or not at all. Limits and the
  initial value that only make sense together go in one operation.
- What a thing is called by others (a variable's `name`, which conditions write) and what it
  is (`type`) are not changed by these: that touches every file that uses it, and comes with
  the operations of block 5.5, as do creating, moving and deleting.

## What refuses an operation

1. **It is not an operation.** Its shape against the schema (`schema.*`, with the `field`),
   a field that belongs to another `op` (`schema.unexpected_field`), the id missing
   (`schema.missing_field`), a field both set and cleared (`operation.set_and_cleared`), a
   text with half a character (`operation.invalid_text`). These issues have no location:
   they are about the operation, not about a file.
2. **What it names is not there.** `operation.unknown_variable`, with the `id`: no `.vars`
   file that can be read has that variable. A project without a manifest, or with one that
   cannot be read, takes no `set_project` (the manifest's own issues).
3. **The file it changes would have a problem of its own that it did not have before**: a
   name too long, a minimum above the maximum, an initial value outside the limits, a step of
   0. The issues are the ones `primum validate` gives, with their place in the file.

## What does not refuse it

A project being built has problems: an element with no pin yet, a schedule before the project
has a time zone. So an operation is **not** refused for what it means to the rest of the
project, nor for problems the file already had. The project that comes back may be invalid;
`load_workspace` lists its problems, and only building a package asks for none.

## How a changed file is written

UTF-8, two spaces of indentation, a line end at the end, and the fields of the changed object
in the order of its schema, so a file reads the same whoever edited it. A file that was
written by hand in another style is written again whole in this one the first time an
operation changes it.

## Not here yet

Undoing (operations are pure, so it is keeping the files of before); who may apply one and
on which revision of the project (the board's API, block 5.4b); operations on files,
elements, sequences and automations (5.5 to 5.7).
