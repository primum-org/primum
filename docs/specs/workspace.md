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
| `.sec` | `sequence` | Tracks of clips per element; blocks that include other sequences; parameters (a component); `priority` and `exclusiveGroup` (decision 0006) |
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

Names of constants and variables are not ids: they follow the scopes of decision 0005
(`variables-and-scopes.md`), which also says how a block's arguments fit the parameters they
name.

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
   make references to what it defines look wrong; then the names and their scopes, the
   components (`variables-and-scopes.md`) and the resources of each board
   (`board-profiles.md`).

Without `project.json` the folder is not a project (`project.manifest_missing`). Warnings do
not make a project invalid; errors do.

## Sequences in time

Each clip of a track runs from `atMs` for `durationMs`, in the time of its sequence; a block
runs the included sequence from its `atMs`, its parameters bound to the block's arguments. For
the checks, a sequence is **flattened**: its own clips plus the clips of what it includes, at
their offsets, each sequence flattened once (`primum_core.overlaps`).

- **Within a sequence**, two clips of one element whose times overlap are an error,
  `track.clips_overlap` (`element`, `atMs`: where the later one starts). It points at the later
  clip, or at the block if the clip comes through one. Two clips that come through the same
  block on the same element of the included sequence are not compared: their overlap belongs
  to it, and is reported there once. Two that only meet because the block bound a parameter to
  an element the component also uses directly are new, and are reported at the block, once per
  element (a component of twenty clips included twice is one problem, not twenty). A clip of
  `durationMs: 0` takes no time and overlaps nothing. Clips that only touch (one ends where the
  next starts) do not overlap. A clip on an element the project does not define is only
  `ref.unknown`.
- **Between sequences**, the engine arbitrates (decision 0006, phase 4): by `priority` (a higher
  one layers over a lower one while it runs; within one priority the latest command wins) and
  by `exclusiveGroup` (starting one sequence of a group stops the others). What can be said
  without the engine is a warning: two sequences that **automations start**, on the **same
  priority**, **not in one exclusive group**, that touch the **same element**, may run at the
  same time: `sequence.may_overlap` (`sequence`, `other`, `element`), once per pair, at the
  second sequence by path. Sequences nothing starts are not compared (those the phone UI or
  the API will start, phase 5, are not known here); a parameter bound to nothing (a component's
  own, or one of a component included without that argument) counts as no element, and so does
  an element the project does not define. An `exclusiveGroup` is one name for the whole
  project, outside the folder scopes of names (`variables-and-scopes.md`): two sequences in any
  folders with the same group are in the same group. The `priority` and `exclusiveGroup` of an
  included sequence play no part when it runs inside another: the including sequence's apply to
  everything it flattens. They matter when the included sequence is started on its own.

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
