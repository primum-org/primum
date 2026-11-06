# Workspace

A project is a folder of files (decision 0004). This spec says what the folder holds, how
`core` reads it and what it checks. Formats: `schemas/`. Code: `primum_core.workspace`.

## The folder

- `project.json` at the root: the manifest (name, description).
- Any number of project files, in any folders, each read by its extension (without regard to
  case: `SHOW.SEC` is a sequence):

| Extension | Kind | Holds |
|---|---|---|
| `.hw` | `hardware` | Boards (`model` names a board profile) and the elements wired to them |
| `.vars` | `variables` | Constants and variables of its folder; names exported and imported |
| `.sec` | `sequence` | Tracks of clips per element; blocks that include other sequences; parameters (a component) |
| `.evt` | `event` | Something from outside: an input element, a button of the phone UI, the local API |
| `.sched` | `schedule` | Times of day (start automations) and windows of time (conditions) |
| `.auto` | `automation` | When events or schedules fire, if a condition holds, do actions |

- Any other file is not part of the project: it is ignored with a warning
  (`file.not_in_format`). Hidden files and folders (`.git`) and links are not read at all.

Every file has `id` (a UUID that never changes), `kind` and `schemaVersion`. So has everything
defined inside a file that others refer to: boards, elements, constants, variables, parameters,
clips and blocks. Times are integer milliseconds; pins are GPIO numbers (BCM).

## References

Files and the things in them refer to each other **by id, never by path**: a file can be
renamed or moved to another folder without breaking anything. Each reference must name
something of the right kind:

| Field | Refers to |
|---|---|
| `.hw` `elements[].board` | a board, of this or another `.hw` file (one file per board is fine) |
| `.vars` `imports[].from` | a `.vars` file |
| `.sec` `tracks[].element` | an element, or a parameter of type `element` of this same sequence |
| `.sec` `blocks[].sequence` | a sequence |
| `.sec` `blocks[].arguments[].parameter` | a parameter of the included sequence |
| `.sec` `blocks[].arguments[].element` | an element, or a parameter of type `element` of this sequence |
| `.evt` `element` | an input element (`digital_input`, `i2c_device`), never an output |
| `.auto` `when[]` | an event or a schedule |
| `.auto` `do[].sequence` | a sequence |

Names of constants and variables are not ids: they follow the scopes of decision 0005 (block
2.4). Whether a block's arguments fit the parameters they name (an element for an element
parameter, a value for the others, each parameter once) is checked with components (2.4).

## Fields that depend on the case

| Object | Case | Needs | Must not have |
|---|---|---|---|
| Element | `digital_output`, `digital_input`, `pwm_output` | `pin` | `bus`, `address` |
| Element | `i2c_device` | `bus`, `address` | `pin`, `activeLow: true` |
| Event | `source: element` | `element`, `trigger` | |
| Event | `source: ui` or `api` | | `element`, `trigger` |
| Action | `start_sequence`, `stop_sequence` | `sequence` | `variable`, `value` |
| Action | `set_variable` | `variable`, `value` | `sequence` |
| Action | `increment_variable` | `variable` (`value`: the amount, 1 if absent) | `sequence` |

## Reading a project

`load_workspace(files)` takes every file as path (relative to the folder) → bytes and returns
the `Workspace` (manifest and files, by path) or the issues that prevent it. Checks come in
stages, so each problem is reported once, where it is:

1. each file on its own: UTF-8, JSON, its schema (`file.*`, `schema.*`), then the fields that
   depend on the case (`schema.missing_field`, `schema.unexpected_field`);
2. once every file reads, the project as a whole: unique ids (`id.duplicate`) and references
   (`ref.unknown`, `ref.wrong_kind`), which need every file: a file that does not read would
   make references to what it defines look wrong.

Without `project.json` the folder is not a project (`project.manifest_missing`). Warnings do
not make a project invalid; errors do. Later blocks add scopes and components (2.4), pins
(2.5) and overlapping sequences (2.6).

## From the command line

    uv run primum validate <folder> [--lang en|es] [--json] [--strict]

It writes each issue with its place, message and hint (English by default, Spanish with
`--lang es`), or JSON with codes, params, places and the text in the chosen language. Scripts
and AI assistants should rely on the codes and params, not on the text. Exit status: 0 valid,
1 problems (warnings count with `--strict`), 2 the command could not run (on stderr).

## The `.primum` file

A whole project is saved or shared as one `.primum` file: a zip of the folder, with
`project.json` at its root. Internal files are never shared on their own. Writing and reading
it comes with the UI (phase 5).
