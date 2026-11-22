# Engine semantics

What the engine does with sequences in time. It grows with phase 4; today it covers which
sequences are running and how a board runs them. Who commands an element given those is in
[`workspace.md`](workspace.md) (decision 0017).

## Which sequences are running (decision 0023)

A sequence is **started** by an automation (`start_sequence`), and later by the phone UI and
the API. A sequence included in another through a block is not started: it is part of the one
that includes it.

- A sequence that does not hold stops running when its last clip ends. One that holds
  (`whenDone: "hold"`) runs until it is stopped.
- Starting a sequence **stops the others of its `exclusiveGroup`**, whatever their priority.
- Starting a sequence that is **already running restarts it**: it begins again and counts as
  started last. With `whenStartedAgain: "ignore"` the start does nothing instead; once the
  sequence has ended, starting it starts it.
- Stopping a sequence that is not running does nothing.
- When the engine starts (boot, a restart of the service, a package activated) no sequence is
  running. Nothing is remembered.

| Written | What happens |
|---|---|
| *On* and *Off*, each an instant command that holds, started at 19:00 and 23:00 every day | On at 19:00, off at 23:00, every day: each start is a new run that started last |
| The same with `whenStartedAgain: "ignore"` on *On* | Off for ever from the second day: *On* never starts last again |
| *Off* as a `fade` to 0, over an *On* that holds | The lamp dims and jumps back to *On* when the fade ends |
| The same with both in one `exclusiveGroup` | Starting *Off* stops *On*; after the fade the lamp is in its safe state |

`primum_core.runs` runs these rules, as `primum_core.commands` runs who commands an element:
`start(running, Running(sequence, started_ms), timelines)`, `stop(running, sequence)` and
`still_running(running, at_ms, timelines)` each give the new list of running sequences, in the
order they were started, which is what `command_at` reads. A `Timeline` carries what they
need: `end` (`None` when the sequence holds), `exclusive_group` and `restarts`. A sequence
that is not of the project is the caller's mistake: `ValueError`.

## Running them on a board (decision 0026)

The runtime runs the sequences of the package it loaded (`deployment-package.md`). Its engine
(`primum_runtime.engine`) keeps the rules above on the package's commands; a test holds it to
`command_at` and `primum_core.runs` on random projects.

Each output has one arbiter, the controller. What it should be at is what the highest of
these with something to say asks:

| Layer | Says | Ends when |
|---|---|---|
| Panic | rest (the safe state) | it is released; nothing comes back |
| A person: manual control | the level of a command of the API without a duration | it is released (`DELETE /api/outputs/{id}`), commanded again, or panic |
| A person: a test | the level of a command with `durationMs` | it runs out, is released, commanded again, or panic |
| The sequences | the command in force of the highest priority, then the one that started last | its time is over, or its sequence is stopped |
| Nobody | rest | |

A person's command replaces the one before on that output, test or not. When a layer ends,
the output goes to what the next one says: a test over a sequence gives the output back to
the sequence.

| Request | Does | Refused |
|---|---|---|
| `POST /api/sequences/{id}/start` | Starts a sequence of the package, by the rules above | `sequence.unknown` (404; also with no package), `panic.active` (409) |
| `POST /api/sequences/{id}/stop` | Stops it; one not running stays so | `sequence.unknown` (404) |
| `DELETE /api/outputs/{id}` | Lets go of an output: manual control or a test is over | `output.unknown` (404) |

The state gives `sequences` (`id`, `name`, `running`, in the order of the package) and, for
each output, `controlledBy`: `manual`, `test`, `sequence` or nothing.

- Panic stops every sequence and ends everything a person asked. While it is on no sequence
  starts.
- The runtime works only at changes: one timer for the next thing due (a test running out, a
  command starting or ending, an output to be tried again). An output is written only when
  the level it should be at changes.
- An output that cannot be taken where it should be does not stop its sequence or the other
  outputs: it says so (`restFailed`) and is tried again every 5 s. So does one whose command
  cannot even be worked out (a value its driver refuses): tests of other outputs still
  expire, they can still be released, and the timer is still told when to come back.
- A sequence the package asks to restart starts from its beginning; when the service starts,
  none is running.

A sequence is started and stopped by the API, and by the automations of the package when an
input changes or an event is fired (`events.md`).

### Fades (decision 0027)

A command whose action moves its element (a `fade`: its driver gives it a `startState`)
takes its output from where the clip starts to where it ends, in a straight line over the
length of the clip: at a time `t` into a clip of length `d`, the level is `start + (end -
start) × t / d`. When the clip is over the output stays where it ends, for as long as the
command is in force.

- The level is worked out from the clock every time, so a step that comes late goes to
  where the fade is by then.
- While a sequence is moving an output the runtime wakes every 20 ms and writes it; the
  rest of the time it wakes only at changes. A fade under a person's hand is not stepped.
  The 20 ms count from the last time the outputs were settled, so a state that keeps
  changing for other reasons (requests, inputs) does not put a step off.
- Without a `from`, the fade starts from the level the output has when the command first
  commands it, whatever took it there. After a command of a sequence, that is where that
  command had the output, by its own time, at the instant it handed it over (where a fade
  ended, or where one that is cut had got to), not the last step written: a fade up followed
  by one down reaches its top whatever its length and however late a step comes. A fade that
  starts under a higher priority is handed the output when that one ends, and starts from
  the level it was left at; its time still counts from when it started, so it joins where
  it would be by then. Held by hand meanwhile, the fade goes on unseen from
  that level, and the output joins it where it is by then when it is let go.
- Listeners are told the state four times a second while only fades move, and when one ends.

### Variables (decision 0027)

The variables of the package start at their initial values when the service starts. The
state gives them (`variables`: `id`, `name`, `type`, `value`, `min`, `max`, `setting`).

| Request | Does | Refused |
|---|---|---|
| `PUT /api/variables/{id}` with `{"value": 40}` | Gives the variable that value | `variable.unknown` (404; also with no package); `variable.value_invalid` (422: `name`, `type`) for a value of another type, or one that is no number (`NaN`, `Infinity`, which Python's JSON reads); `variable.value_out_of_range` (422: `name`, `value`, `min`, `max`) outside its limits. Nothing changes |

An argument that reads a variable takes its value when its command first commands its
output, and keeps it while the command lasts: setting the variable shows the next time such
a command starts. A command that starts while a higher priority has its output reads its
variables when it gets the output.

An automation sets and increments variables too (`events.md`): an increment stays within
the variable's limits.

Not yet: variables marked `persistent` are not kept across a restart (4.4d).

## Schedules and restarts (decision 0023)

- A **time** of a schedule ("at 19:00") is an instant: it starts its automations then, and is
  lost if the board was off.
- A **window** ("from 19:00 to 23:00") starts its automations when it opens, and when the
  engine starts inside it. It is how a light comes back after a power cut.
- Neither fires until the board knows the time.

Decided, not built: schedules come with events and automations, and `events.md` will say the
rest (a clock that becomes reliable late, windows across midnight).
