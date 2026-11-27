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
   text with half a character (`operation.invalid_text`), a number that is none (`NaN`, an
   infinity, an integer too large for any float: `schema.expected_number`). These issues have
   no location: they are about the operation, not about a file. An integer a float holds but
   not exactly (above 2^53) is taken, as reading a file takes it; see the plan.
2. **What it names is not there.** `operation.unknown_variable`, with the `id`: no `.vars`
   file has that variable. Files are looked in as the JSON they hold, whatever problems they
   have; a `.vars` file that is not a JSON object cannot be looked in, and its problem comes
   with `operation.unknown_variable`, as does one whose `variables` is missing or no list. An
   id that two variables have names neither
   (`id.duplicate`): nothing is changed until the project has it once. A project without a
   manifest, or with one that is not a JSON object, takes no `set_project` (its problem).
3. **The object it changes would have a problem of its own that it did not have before**: a
   name too long, a minimum above the maximum, an initial value outside the limits, a step of
   0. The issues are the ones `primum validate` gives about that object, with their place in
   the file: for `set_project` the manifest, for `set_variable` the variable alone. A field
   the schema finds fault with (one it does not know, as a newer Primum may write, or one of
   the wrong type) does not stop the checks of its values: they are made on the variable
   without that field.
4. **The file would keep a number JSON does not have** (`NaN`, `1e999` written in it by
   hand): there is nothing to write it back as. The issues say where those numbers are; an
   operation that replaces them is taken.

## What does not refuse it

A project being built has problems: an element with no pin yet, a schedule before the project
has a time zone. So an operation is **not** refused for what it means to the rest of the
project, nor for problems the file already had, nor for the problems of other objects of its
file: a variable is changed, or fixed, while another of its file has a field of the wrong
type, and a fix that lets a file validate is not blamed for what then shows elsewhere in it.
This is what lets a project uploaded with problems be fixed on the board. The project that
comes back may be invalid; `load_workspace` lists its problems, and only building a package
asks for none.

An operation that changes nothing (every field it gives already has that value, or it gives
none) gives back the files it was given, the same objects: whoever keeps revisions of a
project sees no change.

## How a changed file is written

UTF-8, two spaces of indentation, a line end at the end, and the fields of the changed object
in the order of its schema, so a file reads the same whoever edited it; a field its schema
does not know (a misspelling) is kept, after the others, as a problem to show. A whole number
given with a fraction (`90.0`) is written as reading a file takes it, `90`. A file that was
written by hand in another style is written again whole in this one the first time an
operation changes it.

## Not here yet

Taking away a field the schema does not know: `clear` takes only the fields an `op` may
clear, so such a field stays until a new operation, or a hand, removes it. Undoing (operations are pure, so it is keeping the files of before); who may apply one and
on which revision of the project (the board's API, block 5.4b); operations on files,
elements, sequences and automations (5.5 to 5.7).
