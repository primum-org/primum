# Engine semantics

What the engine does with sequences in time. It grows with phase 4; today it covers which
sequences are running. Who commands an element given those is in
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

## Schedules and restarts (decision 0023)

- A **time** of a schedule ("at 19:00") is an instant: it starts its automations then, and is
  lost if the board was off.
- A **window** ("from 19:00 to 23:00") starts its automations when it opens, and when the
  engine starts inside it. It is how a light comes back after a power cut.
- Neither fires until the board knows the time.

Decided, not built: schedules come with events and automations, and `events.md` will say the
rest (a clock that becomes reliable late, windows across midnight).
