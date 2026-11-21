# Deployment package

What the runtime receives: a project compiled for one board, flat, built only from a project
that passed every check (decision 0024). That does not let a reader trust it: whoever reads a
package checks it again (*Reading one*, below). Its format is `schemas/package.schema.json`. It is built by
`primum_core.compiler.compile_package(workspace)`, with the driver manifests the workspace was
checked against (it keeps them), and from the command line by
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
test holds the numbers to the examples of the RFC. Keys are sorted by their UTF-16 units, as
the RFC asks and JavaScript compares text. The same project always compiles to the same
package, whatever the order its files are given in.

## Reading one

`primum_core.package.read_package(path, content)` reads a package and refuses it, in this
order, for:

1. its text and JSON, then its schema (the codes of any file, `file.invalid_text` for half a
   character among them, which could not be hashed);
2. its hash: `package.hash_mismatch`, at `/hash`. It tells a file cut short or changed by
   hand, and nothing else: a package built wrong has a right hash;
3. not holding together (`check_package`):

| Problem | Code |
|---|---|
| An id twice among elements, variables, sequences, events, schedules and automations | `id.duplicate` |
| A command on an element, an argument or an action on a variable, an action on a sequence, an event on an element or a `when` that the package does not have | `ref.unknown` |
| An argument with neither `value` nor `variable`; an action or an event without a field its case needs | `schema.missing_field` |
| An argument with both; an action or an event with a field that is not of its case | `schema.unexpected_field` |
| A command whose `untilMs` is before its `atMs`, whose action ends after its sequence does (`atMs`), or that is in force beyond it (`untilMs`) | `schema.invalid_value` |
| An option of an element, or an argument of a command, given twice | `config.duplicate`, `action.param_duplicate` |
| A variable with limits that is not a number (`schema.unexpected_field`), with `min` above `max`, or whose `initial` is of another type or outside them | `variable.limits_invalid`, `value.expected_*`, `variable.initial_out_of_range` |
| An action that sets or adds a value of another type, sets one outside the variable's limits, or increments what is not a number | `value.expected_*`, `variable.set_out_of_range`, `variable.not_numeric` |

Not checked here, because it needs the driver manifests and the board profile, which `core`
only gets from its caller: that each action is one of its element's driver and takes its
arguments (a variable read for a parameter is of its type and limited within its limits:
the type and the limits of a parameter are in the manifest), that the options of an element
are its driver's, and that pins and buses are free on the board. **The runtime checks those
when it loads a package** (below), with its own drivers and its HAL, and refuses the package
whole: it never trusts one for having a hash.

## Running one

```
primum-runtime --package <file>        (or PRIMUM_PACKAGE)
```

The service takes its elements and its board from the package (decision 0025), instead of
from `--pin` and the other options of elements: giving both, or a `--board` that is not the
package's, is a mistake of the command line. `primum_runtime.package.load_package` reads the
package and checks it before anything is claimed; any of these and the service does not start
(exit 1, the reason in the log):

| Problem | Code | Params |
|---|---|---|
| The file cannot be read | `package.unreadable` | `path`, `detail` |
| `core` refuses it (*Reading one*) | `package.invalid` | `path`, `problems`: up to five, each a code and where; the log has them all |
| No profile for its board | `package.board_unsupported` | `board`, `available` |
| An element of a type without a driver here | `element.type_unsupported` | `element`, `type` |
| An option its driver or its board does not take | `element.value_*` ([drivers](drivers.md)) | `element`, `name` |
| Two elements on one pin | `package.pin_shared` | `pin`, `elements`: the names of the two |
| A command with an action its element's driver does not have (an input has none) | `element.action_unknown` | `element`, `action`, `available` |
| An argument the action does not take as written | `element.value_*` | `element`, `name` |
| An argument read from a variable of another type, not limited within the parameter's limits, or for a parameter with choices | `element.variable_unfit` | `element`, `action`, `name`, `variable` |
| An argument read from a variable for a number that nothing limits, as a written one | `element.value_unlimited` | `element`, `name` |
| A pin the board lacks or reserves, a PWM channel two pins share | the HAL's, at the claim (`hal.pin_*`, `hal.pwm_*`): the last word, by the pin alone | |

Elements are then asked for by their id: the state gives each output and input its `id` and
its `name`, and a command goes to `PUT /api/outputs/{id}`. The service drives them as it
drove its own (commands, test mode, panic); it starts no sequence yet.

## Not yet

- Running the sequences of the package: block 4.3b. That an event's element is an input: 4.4.
- Activation, rollback and sending a package to a board: block 4.5. Until then the file is
  copied by hand and named in the service's configuration.
- An automation's `if` is the text of the project, its names unresolved, and the constants it
  names are not in the package: the expression language (4.4) replaces it.
- When the engine reads the variable of an argument: block 4.3. So is what it does with a
  value that leaves a variable's limits while running (an increment, a value set from the
  phone): the limits are in the package, and the engine must hold to them on every
  assignment, since a clip that reads the variable counts on it.
- Audio and other files next to the package: phase 6.
- A project on several boards.
