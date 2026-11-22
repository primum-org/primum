# Events and automations

How something that happens outside starts what a project says (decision 0029). Schedules,
their windows and the clock they need come in block 4.4c and will be written here too.

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

## Automations

An automation (`.auto`): **when** one of its events happens, **if** its condition holds,
**do** its actions.

1. It must be `enabled`, and the event one of its `when`.
2. Its condition (`if`, `expressions.md`) is worked out on the values the variables have.
   Without a condition it always holds.
3. Its actions (`do`) are done, in the order it lists them.

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
- firing an event by hand is refused (`panic.active`, 409);
- nothing is kept for later: releasing panic does not replay what happened meanwhile.

## The API

The state (`GET /api/status`, and every message of `/api/ws`) gives, of the package that is
running:

| Field | Of each |
|---|---|
| `events` | `id`, `name`, `source` |
| `automations` | `id`, `name`, `enabled`, `problem` (`null`, or `{code, params}`) |
| `inputs` | also `lostEvents` |

| Request | Does | Refused |
|---|---|---|
| `POST /api/events/{id}/fire` | Makes the event happen: its automations act. Answers with the new state | `event.unknown` (404; also with no package); `event.not_fireable` (409: `id`, `name`) for an event of an element; `panic.active` (409) |

## Not yet

- Schedules (`.sched`), their windows as a condition, and the reliable clock: block 4.4c.
- Variables marked `persistent` kept across a restart: block 4.4d.
- An execution trace of what each event started: block 4.5. Until then, the log.
- The page of the runtime shows neither events nor automations (the UI of phase 5).
- An automation cannot be enabled or disabled while the package runs.
