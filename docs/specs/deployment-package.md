# Deployment package

What the runtime receives: a project compiled for one board, flat, built only from a project
that passed every check (decision 0024). That does not let a reader trust it: whoever reads a
package checks it again (*Reading one*, below). Its format is `schemas/package.schema.json`. It is built by
`primum_core.compiler.compile_package(workspace, drivers)` and from the command line by
`primum build <folder>`; nobody writes one by hand.

## Building

```
primum build <folder> [--output <file>] [--lang en|es]
```

Writes `<folder>.package.json` in the current folder, or `--output`. A `*.package.json`
inside a project folder is not read as part of the project, so `primum build .` can be run
from inside it. A project with errors is
not built (exit 1, the problems as `primum validate` shows them); warnings are shown and it is
built. Exit 2 when the folder cannot be read or the package cannot be written.

A valid project that cannot be a package yet:

| Problem | Code | Params |
|---|---|---|
| No board in any `.hw` file | `package.no_board` | |
| More than one board | `package.several_boards` | `boards` (their names) |

Both are reported at `project.json`.

## What is in it

| Field | Content |
|---|---|
| `kind`, `schemaVersion` | `"package"`, `1` |
| `hash` | `sha256:` and 64 hex digits (below) |
| `project` | `id`, `name` |
| `board` | `id`, `name`, `model` |
| `elements` | Every element: `id`, `name`, `type`, its wiring (`pin`, `activeLow`, `bus`, `address`) and `config` with **every** option of its driver, the defaults of the ones its file does not give |
| `variables` | Every variable: `id`, `name`, `type`, `initial`, `min`, `max`, `persistent`, `setting` |
| `sequences` | Every sequence without parameters (below) |
| `events`, `schedules` | As the project has them, references by id |
| `automations` | `id`, `name`, `enabled`, `when`, `if`, `do`; an action names its `sequence` and its `variable` by **id** |

Not in it: folders, scopes, imports and exports, components, constants, descriptions.

## Sequences

A sequence has `id`, `name`, `priority`, `exclusiveGroup`, `whenDone`, `whenStartedAgain`,
`durationMs` (when its last clip ends) and its `commands`. Components are expanded, their
element parameters bound.

A command is a clip after the rule of decision 0017:

| Field | Meaning |
|---|---|
| `clip` | The id of the clip of the project, for the trace |
| `element` | The element it commands |
| `atMs` | When it starts, in the time of the sequence |
| `durationMs` | How long its action lasts; 0 for an instant command. After it the element stays in the state the action ends in |
| `untilMs` | Until when it is in force. Absent: until the sequence is stopped (what a sequence that holds keeps) |
| `action`, `arguments` | What the element is asked |

`arguments` has one entry per parameter of the action: `{name, value}`, the driver's default
when the clip gives none, or `{name, variable}` with the id of the variable to read. An
optional parameter that the clip leaves out is left out.

Commands are in the order they start; those of one instant by element id, then clip id.

To know what an element is asked at an instant, a reader takes the commands of the running
sequences that are in force (`atMs` ≤ t < `untilMs`), keeps those of the highest `priority`,
then the one that started last, then a command with a length over an instant one, then the
sequence started last. That is all `primum_core.commands.command_at` does, and a test holds
the two together on random projects.

## The hash

`hash` is the sha256 of the package without its `hash` field, as JSON in the canonical form
of RFC 8785 (JSON Canonicalization Scheme), which is what `JSON.stringify` gives for an object
whose keys were sorted:

- object keys sorted, no whitespace (`,` and `:` only), UTF-8, text escaped only where JSON
  requires it;
- numbers as JavaScript writes them: the shortest digits that read back to the same value,
  plain from 1e-6 up to 1e21 (`80`, never `80.0`; `0.00001`) and with an exponent outside
  (`1e-7`, `1e+21`).

`primum_core.package.canonical(value)` writes it and `package_hash(document)` hashes it; a
test holds the numbers to the examples of the RFC. The keys of a package are ASCII, so
sorting them as text is the RFC's order. The same project always compiles to the same
package, whatever the order its files are given in.

## Reading one

`primum_core.package.read_package(path, content)` reads a package and refuses it, in this
order, for:

1. its text and JSON, then its schema (the codes of any file);
2. its hash: `package.hash_mismatch`, at `/hash`. It tells a file cut short or changed by
   hand, and nothing else: a package built wrong has a right hash;
3. not holding together (`check_package`):

| Problem | Code |
|---|---|
| An id twice among elements, variables, sequences, events, schedules and automations | `id.duplicate` |
| A command on an element, an argument or an action on a variable, an action on a sequence, an event on an element or a `when` that the package does not have | `ref.unknown` |
| An argument with neither `value` nor `variable`; an action or an event without a field its case needs | `schema.missing_field` |
| An argument with both; an action or an event with a field that is not of its case | `schema.unexpected_field` |
| A command whose `untilMs` is before its `atMs` | `schema.invalid_value` |

Not checked here, because it needs the driver manifests and the board profile, which `core`
only gets from its caller: that each action is one of its element's driver and takes its
arguments, that the options of an element are its driver's, and that pins and buses are free
on the board. **The runtime checks those when it loads a package** (block 4.3), with its own
drivers and its HAL, and refuses the package whole: it never trusts one for having a hash.

## Not yet

- Activation, rollback and sending a package to a board: block 4.5.
- An automation's `if` is the text of the project, its names unresolved, and the constants it
  names are not in the package: the expression language (4.4) replaces it.
- When the engine reads the variable of an argument: block 4.3. So is what it does with a
  value that leaves a variable's limits while running (an increment, a value set from the
  phone): the limits are in the package, and the engine must hold to them on every
  assignment, since a clip that reads the variable counts on it.
- Audio and other files next to the package: phase 6.
- A project on several boards.
