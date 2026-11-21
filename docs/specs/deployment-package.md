# Deployment package

What the runtime receives: a project compiled for one board, flat and already checked
(decision 0024). Its format is `schemas/package.schema.json`. It is built by
`primum_core.compiler.compile_package(workspace, drivers)` and from the command line by
`primum build <folder>`; nobody writes one by hand.

## Building

```
primum build <folder> [--output <file>] [--lang en|es]
```

Writes `<folder>.package.json` in the current folder, or `--output`. A project with errors is
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

`hash` is the sha256 of the package without its `hash` field, as JSON in canonical form:

- object keys sorted, no whitespace (`,` and `:` only), UTF-8, text not escaped beyond what
  JSON requires;
- a whole number without a fraction or exponent (`80`, never `80.0`); other numbers as the
  shortest text that reads back to the same value.

`primum_core.package.package_hash(document)` computes it and `read_package(path, content)`
reads a package: its text and JSON, its schema, then its hash (`package.hash_mismatch`, at
`/hash`). The same project always compiles to the same package, whatever the order its files
are given in.

## Not yet

- Activation, rollback and sending a package to a board: block 4.5.
- An automation's `if` is the text of the project, its names unresolved, and the constants it
  names are not in the package: the expression language (4.4) replaces it.
- When the engine reads the variable of an argument: block 4.3.
- Audio and other files next to the package: phase 6.
- A project on several boards.
