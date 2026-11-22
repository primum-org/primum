# The trace

What the board did, and why, as it happened (decision 0032). The state says how things
are; the trace says how they got there: "the sensor saw someone, *Welcome* acted, the
sequence started, it ended ten seconds later".

## What an entry is

An entry is a **decision**, not a measurement: something happened, an automation acted or
did not, a sequence started or ended, a person commanded an output, panic. The level of
each output is the state's to tell, and the steps of a fade are in neither.

| Field | |
|---|---|
| `number` | From 1, growing by one, never used again while the service runs |
| `atMs` | When, in milliseconds since the service started, on the clock that never jumps |
| `time` | The time of day (ISO 8601, UTC) when the board knows it (`events.md`); `null` until then |
| `kind` | What it is: a stable code, as an error's |
| `params` | What it is about: ids, names, values. Never text |
| `cause` | The number of the entry that led to it, if one did |

`cause` is what answers "why": an automation's entry names the event that concerned it, and
a sequence started by an automation names that automation's entry.

## Kinds

| Kind | When | Params |
|---|---|---|
| `service.started` | The service starts: always entry 1 | `project`, `package` (its hash), with a package |
| `event.happened` | An input changed, an event was fired, a schedule happened | `id`, `name`, `source` (`element`, `ui`, `api`, `schedule`) |
| `event.ignored` | It happened while panic was on | the same, and `reason`: `panic` |
| `event.failed` | It could not be dealt with at all | the same; `cause`: the event |
| `automation.acted` | Its condition held; its actions follow | `id`, `name`; `cause`: the event |
| `automation.did_not_act` | Its condition was false, or a window it needs is closed | `id`, `name`; `cause`: the event |
| `automation.failed` | Its condition could not be worked out, or an action failed | `id`, `name`, `problem` (the code its state has), and that problem's own params (`reason`; or `action` and `failure`, the code of what the action failed with); `cause`: the event |
| `sequence.started` | A sequence starts running | `id`, `name`, `by` (`api`, `automation`), `restarted` when it was running; `cause`: the automation |
| `sequence.stopped` | It was stopped | `id`, `name`, `by` (`api`, `automation`, `panic`, or `exclusive_group` when one of its group started) |
| `sequence.ended` | It reached its end on its own | `id`, `name` |
| `variable.changed` | A variable was set or incremented | `id`, `name`, `value` (after), `by` (`api`, `automation`); `cause`: the automation |
| `output.commanded` | A person commanded an output | `id`, `name`, `action`, `durationMs` for a test |
| `output.released` | A person let go of one they held | `id`, `name` |
| `output.test_ended` | A test ran out | `id`, `name` |
| `output.failed` | An output could not be taken where it should be (said once, not at every retry) | `id`, `name` |
| `output.recovered` | It got there after all | `id`, `name` |
| `panic.on`, `panic.released` | Panic is latched, released | |
| `time.known`, `time.unknown` | The board comes to know the time, or stops knowing it | |
| `variables.unsaved`, `variables.saved` | Persistent values could not be kept, are kept again | |

- A request that is refused (an unknown output, an event fired during panic) notes nothing:
  nothing happened.
- A sequence that ended while nobody was looking is noted, as ended, before whatever is
  noted next.
- When an automation acts, what its actions did follows it, in order: variables changed,
  then the sequences that stopped and started.
- A sequence restarted in the very millisecond it started is not noted again.

New kinds may be added; whoever reads the trace ignores the ones it does not know.

## How much is kept

The last **1000 entries**, in memory. Older ones are dropped. The trace starts empty when
the service starts: what happened before is in the journal (`journalctl -u primum`).
Nothing is written to the card for it.

## The API

| Request | Answers |
|---|---|
| `GET /api/trace` | `{entries, first, last}`: every entry kept, oldest first |
| `GET /api/trace?after=<number>` | Only the entries numbered above it: what is new since the last one the caller has |
| WebSocket `/api/trace/ws` (`?after=<number>`) | A message as above with what is kept (above `after`), then one with each new entry or entries as they are noted |

`first` is the oldest entry still kept and `last` the newest ever noted. A caller that asks
for what follows entry `n` and finds `first` above `n + 1` missed the entries in between:
they were dropped before it asked.

A slow client of the WebSocket holds nothing up: it is sent, when it can take it, what is
kept above the last entry it has.

## Not yet

- Texts for the kinds in the catalogs, and the trace on a page: the UI of phase 5.
- A trace kept across restarts.
- Which package was activated, and when one was put back: block 4.5b.
