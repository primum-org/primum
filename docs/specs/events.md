# Events and automations

How something that happens outside starts what a project says: an input, a request, or the
time of day (decisions 0029 and 0030).

## Events

An event (`.evt`) is something that happens outside. Its `source` says where it comes from:

| Source | Happens when | Fired by hand |
|---|---|---|
| `element` | Its input element turns `on` (pressed, detected) or `off`, as its `trigger` says | Never |
| `ui` | A person asks, from the app | `POST /api/events/{id}/fire` |
| `api` | A program asks | `POST /api/events/{id}/fire` |

Sequences never make events happen: nothing a project does can start itself again.

### What an element tells

An event listens to an element for something its driver says the element tells: `triggers`
in the driver's manifest (`drivers.md`), `on` and `off` for a `digital_input`.

| Checked | Code | Where |
|---|---|---|
| By `primum validate`: the element is of a type that is listened to, not an output | `ref.wrong_kind` | the event's `element` |
| By `primum validate`: its driver tells that trigger (an element whose type has no driver tells nothing) | `event.trigger_unavailable` (`element`, `trigger`, `available`) | the event's `element` |
| By the runtime, before it runs a package: the same, with its own drivers | `event.not_listenable` (`event`, `element`, `trigger`, `available`, `id`) | the package is refused whole |

### An input on a board

- The runtime reads every change of an input from the kernel, with the edge it was, so a
  press shorter than any polling is still seen.
- A change is an event only if it changes the state the input was in: a pulse too short for
  the kernel to tell its edges apart starts nothing.
- Bounces are filtered by the input itself: `debounceMs` of the `digital_input` (20 ms by
  default, `drivers.md`), in the kernel.
- The kernel keeps a bounded number of unread changes and drops the oldest of a longer
  burst. The state of the input is still right, but the changes dropped started nothing:
  they are counted, logged, and told in the input's state (`lostEvents`).
- A service that was held up deals, when it comes back, with every change that waited, one
  after another and all at that instant: 300 changes are 300 events, not one.
- When the service starts, the state an input is in is read and starts nothing: only a
  change is an event.

## Schedules

A schedule (`.sched`) is the time of day making something happen. An automation waits for
one in its `when`, as for an event.

- A **time** (`times`: days and `at`) is an instant: every listed day at that time.
- A **window** (`windows`: days, `from`, `to`) is open from its start until its end, the end
  not included. One whose end is before its start crosses midnight and belongs to the day
  it opens: Friday 22:00 to 02:00 is open until 02:00 on Saturday. One that starts and ends
  at the same time is refused (`schedule.window_empty`).

A schedule **happens**, and its automations act:

| When | |
|---|---|
| The clock passes one of its times | Once |
| One of its windows opens | Once: it had no window open the last time the service looked, and now it has |
| The board comes to know the time inside one of its windows | When the service starts there, or when the clock is first set there. How a light comes back after a power cut (decision 0023) |

A service that restarts inside a window starts its automations again each time: nothing is
remembered across a restart.

### The time zone

The times of a project are in the project's time zone: `timeZone` in `project.json`, by its
IANA name (`Europe/Madrid`), carried in the package. The same package does the same on any
board, however its system is set up.

| Checked | Code |
|---|---|
| A project with schedules says its time zone | `project.time_zone_missing`, at `/timeZone` of `project.json` |
| `primum validate`: the zone is one the system it runs on knows (not checked on a system without the time zone database) | `project.time_zone_unknown` (`timeZone`) |
| The runtime, before it runs a package: its own system knows the zone | `package.time_zone_unknown` (`timeZone`); the package is refused whole |

### A clock that can be trusted

A Raspberry Pi 4 has no clock with a battery: it starts at some old time and is right only
once it has been set from the network. Until the board knows the time, **no schedule
happens**.

- The time is known once the system has set its clock from the network since it booted
  (systemd-timesyncd leaves `/run/systemd/timesync/synchronized`), or at once when the
  service is told to trust the clock: `--trust-clock`, `PRIMUM_TRUST_CLOCK=1`, for a board
  with a clock of its own.
- Once known, it stays known for as long as the service runs, also if that file goes:
  restarting systemd-timesyncd removes it until it next sets the clock, and the clock is no
  worse for that.
- The state says so: `timeKnown`, and `open` of each schedule is `null` until then. Both are
  as the service last looked, so the state never says more than the service has acted on:
  the time may be set up to 10 s before `timeKnown` says so, and then what is due happens
  in that same look. Listeners are told when the time comes to be known and when a window
  opens or closes, also when nothing happens for it.
- While it is not known the service asks again every 10 s. Once it is, it looks at the
  schedules as each minute turns: their times are whole minutes.

| What the clock does | Then |
|---|---|
| The time comes to be known late (no network at 19:00, set at 19:40) | Windows that are open happen. Times that passed meanwhile are lost, as if the board had been off |
| It jumps forward, or the service did not look for more than 90 s | The times jumped over are lost. A window that opened meanwhile and is still open happens |
| Summer time starts (02:00 becomes 03:00) | A time in the hour that does not exist (02:30) is lost. One right after it (03:00) happens: the gap is counted in the time that really went by, a minute, not in what the clock on the wall jumped. A window that starts in that hour (from 02:30) opens at 03:00: it is open then and was not at the look before |
| Summer time ends (03:00 becomes 02:00 again), or the clock is set back up to two hours | Nothing happens again until the clock is past where it was: a time happens once, and a window that opened in that hour does not open again |
| It is set back further | The time is taken as newly known: windows that are open happen |

Durations (clips, fades, tests) never use this clock: they count on a monotonic one, and a
jump of the time of day does not touch a sequence that is running.

### Windows as a condition

An automation may name schedules in `during`: it only acts while **every one of them has a
window open**. "When the sensor sees someone, during opening hours, start the welcome."

- `during` names schedules, each with at least one window (`ref.wrong_kind`,
  `automation.during_without_windows`).
- It is judged before the condition: with a window closed, the `if` is not worked out.
- While the time is not known nobody can say whether it should act: it does not, and that is
  told as a condition that failed (`automation.condition_failed`, `reason`: `time_unknown`).

## Automations

An automation (`.auto`): **when** one of its events or schedules happens, **during** the
windows it names, **if** its condition holds, **do** its actions.

1. It must be `enabled`, and the event or the schedule one of its `when`.
2. Every schedule of its `during` has a window open (above). Without `during`, the time
   does not matter.
3. Its condition (`if`, `expressions.md`) is worked out on the values the variables have.
   Without a condition it always holds.
4. Its actions (`do`) are done, in the order it lists them.

### Several automations on one event

**Every condition is worked out first, on the same values**: those the variables had when
the event came, before any automation acted. Then the automations that hold act, one after
another in the order of the package, each doing all its actions.

So which automations act never depends on their order. With `visits` at 2 and a limit of 3:

```
Welcome   if visits < 3    do: start the show, visits + 1
Full      if visits >= 3   do: stop the show
```

a press welcomes the third visitor and does not also stop the show: *Full* was judged with
the 2 there were. It acts on the next press.

Two events never mix: one is dealt with whole, conditions and actions, before the next.

### Actions

| Action | Does |
|---|---|
| `start_sequence` | Starts the sequence, as the API does (`engine-semantics.md`): one that is running restarts, unless it ignores that; its exclusive group stops |
| `stop_sequence` | Stops it; one that is not running stays so |
| `set_variable` | Gives the variable the value (checked when the project is validated: of its type, within its limits) |
| `increment_variable` | Adds `value` to it, or 1 when the action has none; a negative value takes away |

**An increment stays within the limits of its variable**: one that would pass a limit leaves
the variable at that limit. A counter with a maximum of 100 stays at 100. The result is of
the variable's type: an `integer` stays a whole number at its limit (`3`, never `3.0`), and
within limits that are not whole (`3` for a maximum of 3.5). Without a limit on that side,
an `integer` stops at `9007199254740991`, the largest a condition can read
(`expressions.md`), and a `number` at the largest there is.

An increment is one operation on the value the variable has: never a value read at one
moment and written at another. Two events cannot lose a count.

An automation never writes an output. It starts and stops sequences, and the controller
arbitrates them with everything else (`engine-semantics.md`): what a person holds stays
held, and a sequence an automation starts shows when it is let go.

### When something goes wrong

| What | Then |
|---|---|
| The condition cannot be worked out (a division by zero, a number at or past 2^53) | It does not hold: the automation does nothing. `automation.condition_failed` (`automation`, `reason`: `division_by_zero` or `overflow`) |
| An action fails | The actions after it are still done, and so are the other automations. `automation.action_failed` (`automation`, `action`, and `problem`, the code of what failed, when it has one) |

Either is logged, once, and stays in the automation's state (`problem`, as an error is
told: `code` and `params`) until an event next concerns the automation and nothing goes
wrong: it acts cleanly, or its condition is worked out and is false. Events it does not wait
for leave it as it is.

Whatever else goes wrong dealing with an event is logged and ends with that event: the
next one is dealt with as any, and the inputs go on being listened to.

### Panic

While panic is on (`safety.md`), what happens starts nothing:

- the inputs are still read, and their state is still told, but no automation acts;
- a schedule that happens meanwhile starts nothing either, and a window that opened during
  panic does not happen when panic is released;
- firing an event by hand is refused (`panic.active`, 409);
- nothing is kept for later: releasing panic does not replay what happened meanwhile.

## The API

The state (`GET /api/status`, and every message of `/api/ws`) gives, of the package that is
running:

| Field | Of each |
|---|---|
| `events` | `id`, `name`, `source` |
| `automations` | `id`, `name`, `enabled`, `problem` (`null`, or `{code, params}`) |
| `schedules` | `id`, `name`, `open` (a window of it is open now; `null` while the time is not known) |
| `timeKnown` | Whether the board knows the time |
| `inputs` | also `lostEvents` |
| `revision` | A number above that of every state the service reported before, by the answer to a command or by the WebSocket, whatever package runs. Two states may cross on their way to a device: the one with the higher number is the later. It starts over when the service restarts |

When nothing changes for 2 s, `/api/ws` sends the state again, with a new `revision`: a
board that is frozen or out of reach closes nothing, and whoever listens can only tell by
its silence. The web UI takes 6 s without a word for a board that is gone.

| Request | Does | Refused |
|---|---|---|
| `POST /api/events/{id}/fire` | Makes the event happen: its automations act. Answers with the new state | `event.unknown` (404; also with no package); `event.not_fireable` (409: `id`, `name`) for an event of an element; `panic.active` (409) |

## Not yet

- The time given by a client (a phone on the local network) for a board that never has
  Internet: today such a board needs `--trust-clock` and a clock of its own.
- Once per window across restarts: it would need something kept on disk.
- A window that opened during panic is not caught up with when panic is released.
- Variables marked `persistent` kept across a restart: block 4.4d.
- The page of the runtime shows neither events nor automations (the UI of phase 5).
- An automation cannot be enabled or disabled while the package runs.
