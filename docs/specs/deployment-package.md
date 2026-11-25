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
| `timeZone` | The time zone of the project's schedules, when it has any |
| `board` | `id`, `name`, `model` |
| `elements` | Every element: `id`, `name`, `type`, its wiring (`pin`, `activeLow`, `bus`, `address`) and `config` with **every** option of its driver, the defaults of the ones its file does not give |
| `variables` | Every variable: `id`, `name`, `type`, `initial`, `min`, `max`, `persistent`, `setting` |
| `sequences` | Every sequence without parameters (below) |
| `events`, `schedules` | As the project has them, references by id |
| `automations` | `id`, `name`, `enabled`, `when`, `during` (schedules, by id), `if`, `do`; an action names its `sequence` and its `variable` by **id**; `if` is the condition compiled to a program (`expressions.md`): constants are values, variables go by id |

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

## On a board: stored, activated, put back (decision 0033)

A service told neither a package file nor pins runs **the package that was activated on
it**, and takes others through its API. It is how a board is meant to run.

| Request | Does | Refused |
|---|---|---|
| `GET /api/package` | `{running, active, previous, staged, problem, fixed}`: each package as `{hash, project}` | |
| `PUT /api/package`, the body the `.package.json` | Checks it against this board (*Running one*, below) and keeps it as the **staged** one, replacing the one staged before. Nothing that runs changes, and nothing waits: the check is off the event loop (a second for a show of 3000 clips) | What is wrong with it (422: `package.invalid`, `element.*`, `event.not_listenable`, `package.board_unsupported` for another board than this service's…); `package.too_large` (413, over 8 MiB); `package.unwritable`; `package.fixed` (409) |
| `POST /api/package/activate` with `{"hash": "sha256:…"}` | Runs a package that is kept: the staged one, or the previous one. The one that ran becomes the previous one | `package.not_stored` (404); `panic.active` (409); `package.fixed` (409); what is wrong with it, read again; `package.unwritable` (500) when the board cannot write which package is active: that is written first, and then nothing is touched; `package.activation_failed` (500: `hash`, `problem`) |
| `POST /api/package/rollback` | Activates the previous one: the two swap, so it can be undone | `package.no_previous` (409); the rest as activating |

- **Two steps, on purpose**: storing never changes what a board does, and activating names
  the package by its hash. Until the API has its PIN (phase 5), that is all that stands
  between a request and the hardware.
- **Activating stops everything and starts from nothing**: sequences stop, what a person
  held is let go, every output goes to its safe state and is released, and the package
  claims its own elements. Also the outputs both packages have: they go through their safe
  state.
- **What carries over**: the persistent variables, which are the project's (a package put
  back finds the values its project has now, if it still takes them, also after a package
  of another project ran in between: `engine-semantics.md`), and
  the trace, which notes `package.stored`, `package.activated` and `package.refused`.
- **A package that cannot be started is not activated**: what ran before is started again
  and stays active; the package stays staged.
- **In this order**: the package is read and checked again (off the event loop), the board
  writes that it is the active one, what runs is closed and the package is started. If the
  write fails nothing has changed. If the start fails, what ran before runs again and the
  board writes back which package is active.
- **Not while panic is on**: release it first.
- **At most three packages are kept**, in `packages/` under the data directory, each in a
  file named by its hash, with a `state.json` that says which is active, previous and
  staged, and the name of the project of each: `GET /api/package` reads that file and no
  package. A kept package is read and checked again each time it is activated or started.
- **A service with nothing it can run starts empty**: no package activated yet, or the
  active one no longer reads, no longer fits, or cannot be claimed (a line another program
  holds, a PWM controller that is missing). Nothing moves, `running` is `null`, and
  `problem` says why. Whatever is wrong with the active package, the service starts.
- `fixed` is true on a service started with `--package` or `--pin`: it runs that and takes
  no packages.

## Running one

```
primum-runtime                         runs what was activated on the board
primum-runtime --package <file>        (or PRIMUM_PACKAGE) runs that file, for development
```

The service takes its elements and its board from the package (decision 0025), instead of
from `--pin` and the other options of elements: giving both, or a `--board` that is not the
package's, is a mistake of the command line. `primum_runtime.package.load_package` reads the
package and checks it before anything is claimed; any of these and the service does not start
(exit 1, the reason in the log; also when it is the HAL that refuses, inside the server's
startup, where uvicorn would exit with a 3 of its own):

| Problem | Code | Params |
|---|---|---|
| The file cannot be read | `package.unreadable` | `path`, `detail` |
| `core` refuses it (*Reading one*) | `package.invalid` | `path`; `problems`, the codes of up to five, and `pointers`, where each is, in the same order; the log has them all |
| No profile for its board | `package.board_unsupported` | `board`, `available` |
| An element of a type without a driver here | `element.type_unsupported` | `element`, `type` |
| A `pwm_output` wired active low, should one get past `core` | `element.active_low_unsupported` | `element`, `type` |
| An option its driver or its board does not take | `element.value_*` ([drivers](drivers.md)) | `element`, `name` |
| An element wired as the board does not allow, by the rules `core` checks a project with: a pin the board lacks, reserves or gives to a bus, two elements on one pin, a PWM output where the board has no hardware PWM or on a channel another has | `element.wiring_refused` | `element`, `pin`, `problem` (`core`'s code: `pin.reserved`, `pin.in_use`…), `other` when another element is in the way |
| A command with an action its element's driver does not have (an input has none) | `element.action_unknown` | `element`, `action`, `available` |
| An argument the action does not take as written | `element.value_*` | `element`, `name` |
| An argument read from a variable of another type, not limited within the parameter's limits, or for a parameter with choices | `element.variable_unfit` | `element`, `action`, `name`, `variable` |
| An argument read from a variable for a number that nothing limits, as a written one | `element.value_unlimited` | `element`, `name` |
| A line the kernel will not give (another program holds it), a PWM controller that is missing | the HAL's, at the claim (`hal.*`), by the pin alone. The HAL knows nothing of reserved pins: it is the last word, not the check | |

Everything wrong is found and logged, not only the first thing; the first is the error the
service ends with. An error about an element of a package carries its `id` next to its name
(`element`): two elements may share a name. The same wiring rules hold for elements told of
by options (`--pin 0` is refused: GPIO 0 is reserved).

Elements are then asked for by their id: the state gives each output and input its `id` and
its `name`, and a command goes to `PUT /api/outputs/{id}`. The service drives them as it
drove its own (commands, test mode, panic); it starts no sequence yet.

## Not yet

- How a board runs the sequences of a package, its fades and its variables is in
  `engine-semantics.md`; its events and automations, in `events.md`.
- Pairing: whoever reaches the API can store and activate a package. The PIN of phase 5.
- A service started with `--package` and a file it cannot run does not start, and systemd
  restarts it without end. A board runs without that option.
- Audio and other files next to the package: phase 6.
- A project on several boards.
