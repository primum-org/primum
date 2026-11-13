# Workspace

A project is a folder of files (decision 0004). This spec says what the folder holds, how
`core` reads it and what it checks. Formats: `schemas/`. Code: `primum_core.workspace`.

## The folder

- `project.json` at the root: the manifest (name, description).
- Any number of project files, in any folders, each read by its extension (without regard to
  case: `SHOW.SEC` is a sequence):

| Extension | Kind | Holds |
|---|---|---|
| `.hw` | `hardware` | Boards (`model` names a board profile) and the elements wired to them, each with the options of its driver (`config`) |
| `.vars` | `variables` | Constants and variables of its folder; names exported and imported |
| `.sec` | `sequence` | Tracks of clips per element, each clip an action of the element's driver with its `arguments`; blocks that include other sequences; parameters (a component); `priority` and `exclusiveGroup` (decision 0006); `whenDone` (`end` or `hold`, decision 0017) |
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

`load_workspace(files, profiles, drivers)` takes every file as path (relative to the folder) →
bytes, the board profiles by model and the driver manifests by element type (`core` reads no
files: the caller loads them), and returns the `Workspace` (manifest and files, by path) or the
issues that prevent it. Checks come in stages, so each problem is reported once, where it is:

1. each file on its own: UTF-8, JSON, its schema (`file.*`, `schema.*`), then the fields that
   depend on the case (`schema.missing_field`, `schema.unexpected_field`) and the configuration
   of each element against its driver (`config.*`, `drivers.md`);
2. once every file reads, the project as a whole: unique ids (`id.duplicate`) and references
   (`ref.unknown`, `ref.wrong_kind`), which need every file: a file that does not read would
   make references to what it defines look wrong; then the names and their scopes, the
   components (`variables-and-scopes.md`), the action of each clip against the driver of its
   element (`action.*`, `drivers.md`), the clips and sequences that overlap (below) and the
   resources of each board (`board-profiles.md`).

Without `project.json` the folder is not a project (`project.manifest_missing`). Warnings do
not make a project invalid; errors do.

## Sequences in time

Each clip of a track runs from `atMs` for `durationMs`, in the time of its sequence; a block
runs the included sequence from its `atMs`, its parameters bound to the block's arguments. For
the checks, a sequence is **flattened**: its own clips plus the clips of what it includes, at
their offsets, each sequence flattened once (`primum_core.timeline`).

What a clip does (decisions 0016 and 0017):

- **A command is in force while it lasts.** A clip with a length, for its length. A clip of
  `durationMs: 0` is an **instant command**: the element takes the state the action ends in (a
  `fade`, its `to`) and keeps it until the next instant command of that element in its own
  sequence, the one it is written in, or until that sequence ends. Included as a block, that
  is the end of the block: a sequence does the same included as started on its own.
- **Who commands an element**: of the commands in force on it, those of the highest
  `priority` count, and among them the one that **started last** wins, within a sequence as
  between sequences. Two that started in one instant: a clip with a length wins over an
  instant command, then the sequence started last. With nothing in force, the element is in
  its driver's safe state. So:
  - a clip plays over an instant command that started before it and gives the element back
    to it when it ends: `on` at 0 s and `set(30)` from 5 to 6 s is on, dimmed for a second,
    on again;
  - an instant command inside a clip cuts it;
  - to leave an element somewhere else after a clip, an instant command goes where the clip
    ends (a `fade` to 0, then an instant `off`). Without it, a `fade` to 0 in the middle of a
    sequence gives the element back to a standing `on`; `core` does not warn about it yet.
- **A sequence ends when its last clip ends**, an instant clip ending where it starts, unless
  it **holds** (`whenDone: "hold"`): then it stays as it is in its last instant until it is
  stopped (an automation's `stop_sequence`, another sequence of its exclusive group starting,
  stop or panic). Every command in force just before its end stays in force: its instant
  commands, and the clips that end with it, each in the state its action ends in. A clip that
  ended earlier is not kept. `whenDone` is ignored when the sequence is included in another.

`primum_core.commands` runs these rules, for tests today and for the engine to agree with
(phase 4): `timelines_of(workspace)` prepares the sequences of a valid project, and
`command_at(element, at_ms, running, timelines)` gives the command in force on an element at
an instant, or nothing (its safe state). `running` are the sequences started and not stopped,
each with when it started, in the order they were started; the caller keeps that list, so
exclusive groups and stopping are not this function's. A command says its clip, the sequence
it is from, since when, and whether it is `settled`: the action is over and the element stays
where it ends (an instant command, or a clip held by a sequence that holds).

The checks (`primum_core.overlaps`):

- **Within a sequence**, two clips with a length of one element whose times overlap are an
  error, `track.clips_overlap` (`element`, `atMs`: where the later one starts), and so are
  two instant commands of one element in the same millisecond. An instant command and a clip
  with a length never overlap: the one that started last commands. It points at the later
  clip, or at the block if the clip comes through one. Two clips that come through the same
  block on the same element of the included sequence are not compared: their overlap belongs
  to it, and is reported there once. Two that only meet because the block bound a parameter to
  an element the component also uses directly are new, and are reported at the block, once per
  element (a component of twenty clips included twice is one problem, not twenty). Clips that
  only touch (one ends where the next starts) do not overlap. A clip on an element the project
  does not define is only `ref.unknown`.
- **An instant command that is the last thing of its own sequence** is never seen: its
  sequence ends there, started on its own or included in the middle of another. A warning,
  `clip.instant_at_end` (`sequence`: the one it is written in, `element`, `action`), at the
  clip, or at the block that gives a component its element. Not reported: what a sequence
  that holds keeps; one that asks for the safe state of its element's driver after something
  else (an instant `on`, and an instant `off` to end with: the element goes there anyway),
  though a sequence that is only that, and so lasts no time, is reported; one that another
  element's later clip keeps alive; and two of one element in that instant (they overlap:
  that error is enough). The safe state is told by the name of the action: `core` does not
  know where an action leaves its element, so an instant `set` to a level of 0 at the end is
  reported although it does what `off` does.
- **Between sequences**, the engine arbitrates (decision 0006, phase 4): by `priority` (a higher
  one layers over a lower one while it runs; within one priority the latest command wins) and
  by `exclusiveGroup` (starting one sequence of a group stops the others). What can be said
  without the engine is a warning: two sequences that **automations start**, on the **same
  priority**, **not in one exclusive group**, that touch the **same element**, may run at the
  same time: `sequence.may_overlap` (`sequence`, `other`, `element`), once per pair, at the
  second sequence by path. If one of the shared elements has an **exclusive** driver (one
  sequence owns it while it runs: `conflictPolicy` in `drivers.md`), it is an error instead,
  `sequence.exclusive_element_shared`, with the same params and that element named. Sequences
  nothing starts are not compared (those the phone UI or
  the API will start, phase 5, are not known here); a parameter bound to nothing (a component's
  own, or one of a component included without that argument) counts as no element, and so does
  an element the project does not define. An `exclusiveGroup` is one name for the whole
  project, outside the folder scopes of names (`variables-and-scopes.md`): two sequences in any
  folders with the same group are in the same group. The `priority`, `exclusiveGroup` and `whenDone` of an
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
