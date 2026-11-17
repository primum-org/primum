# Drivers

A driver implements an element type on a platform. What it offers is described by a
**manifest**: data that `core` reads to check a project without hardware, and that the UI will
read to show what each element can do. One file per element type in `drivers/`
(`drivers/pwm_output.json`), named after the type. Format: `schemas/driver.schema.json`.
The implementations live in the runtimes ([below](#on-a-board-the-runtime)). Why: decisions
0016, 0018 and 0019.

## Contents

| Field | Meaning |
|---|---|
| `id`, `kind` (`driver`), `schemaVersion` (1) | As every file format |
| `elementType` | The type of the elements it serves, as `.hw` files write it (`pwm_output`): the file name |
| `actions` | What a clip may ask of the element, each with a `name`, its `parameters` and the state it leaves the element in (`endState`, and `startState` for one that moves it). None for an element that only reads |
| `config` | The options an element of this type takes in a `.hw` file, beyond its wiring |
| `safeState` | The action the element rests in when nothing commands it, on stop and on panic |
| `conflictPolicy` | `latest_wins` (lights, relays) or `exclusive` (motors, servos: one sequence owns the element while it runs) |

A manifest declares only what something reads. The capabilities of an element (`switch`,
`level`: `docs/architecture.md`) and the platforms that implement a driver are not fields yet:
each comes with its first reader (`docs/plan.md`).

A parameter of an action and an option of the configuration are written the same way:

| Field | Meaning |
|---|---|
| `name` | How clips and elements name it (`level`, `frequencyHz`): a lowercase letter, then letters and digits |
| `type` | `number`, `integer`, `boolean` or `text` |
| `min`, `max` | Its limits on every board (numbers only, both or neither). What only a board limits is in its [profile](board-profiles.md) |
| `choices` | The values it allows (texts only) |
| `default` | The value it takes when not given. Without one it must be given |

The state of an element is a level, from 0 (off) to 100 (fully on). Each action says the one
it leaves its element in, its `endState`: the level itself (`on` is 100, `off` is 0) or the
name of the parameter that gives it (`set` its `level`, `fade` its `to`). It is what an instant
command sets and where a clip with a length ends. An action that moves its element from one
state to another over its clip also says where it starts, its `startState` (`fade` its
`from`); without one, the action holds its end state for the whole clip.

## Rules

The schema checks the shape; `core` (`primum_core.drivers`, run by
`primum_core.formats.read_driver`) checks the rest, each with its code:

- each action has its own name (`driver.duplicate_action`), and so has each parameter of an
  action and each option (`driver.duplicate_parameter`);
- limits only on numbers and in pairs, choices only on texts (`schema.unexpected_field`,
  `schema.missing_field`), whole numbers for an `integer` (`value.expected_integer`), the
  minimum not above the maximum (`driver.limits_invalid`);
- a default of the parameter's type (`value.expected_*`), within its limits or among its choices
  (`driver.default_not_allowed`);
- a state given by a parameter names a `number` or `integer` parameter of its action
  (`driver.unknown_state_parameter`) whose limits are within 0 and 100
  (`driver.state_not_a_level`); a fixed one is from 0 to 100 (the schema);
- a driver with actions has a `safeState` and a `conflictPolicy` (`schema.missing_field`), and
  the safe state is one of its actions that needs no arguments (`driver.unknown_safe_state`); a
  driver without actions has neither (`schema.unexpected_field`).

The manifests ship with Primum and its tests read them, so a broken one is a bug, not a
problem of a project. `primum_core.formats.read_drivers` reads them all (`core` reads no
files: the caller passes each file's content) into what `load_workspace` takes, each by its
own `elementType` whatever its file is called; two of one type are refused
(`driver.duplicate_type`). The CLI uses it, and so will the runtime.

## The drivers of this version

| Type | Actions | Options (default) | Safe state | Conflicts |
|---|---|---|---|---|
| `digital_output` | `on`, `off` | | `off` | latest wins |
| `pwm_output` | `on`, `off`, `set(level)`, `fade(from, to)` | `frequencyHz` (1000), limited by the board | `off` | latest wins |
| `digital_input` | none | `pull` `up`, `down` or `none` (no default: required); `debounceMs` 0–10000 (20) | | |

- A `level`, and the `from` and `to` of a fade, are percentages: 0 to 100, decimals allowed.
- An input says its `pull`: it has no default, because every default is wrong for some wiring
  and a wrong one reads the input as active at rest. A button to ground is `pull` `up` and
  `activeLow` `true`; a button to 3V3 is `pull` `down`; a sensor that drives the line is
  `none`. `core` does not warn about a pull at the active level: it is how a normally closed
  switch is wired, so that a broken wire reads as active.
- On a PWM output `on` is the level 100 and `off` the level 0; on a digital output they are
  its two states (which electrical level is "on" is the element's `activeLow`).
- `fade` goes from one level to the other over the length of its clip; as an instant clip it
  jumps to `to`.
- A manifest holds what is true on every platform: that an option exists, its type, its
  default, and the limits Primum itself sets. `debounceMs` goes from 0 to 10 s on every
  board: no board limits it (the kernel takes up to some 71 minutes and a Raspberry Pi
  debounces in software), so the limit is Primum's own. `frequencyHz` has no limit here:
  which frequencies a PWM takes is the board's, in its [profile](board-profiles.md).
- `i2c_device` has no driver yet (phase 6): it takes no actions and no options.

## What `core` checks in a project

Callers load the manifests (`core` reads no files) and pass them, by element type, to
`load_workspace`. A type without a manifest takes no actions and no options.

**The configuration of an element** (`.hw`, `elements[].config`: a list of `name` and `value`),
checked when its file is read (`primum_core.config`); `element` and `option` in every case:

| Problem | Code | Also |
|---|---|---|
| An option its driver does not have | `config.unknown` | |
| An option given twice | `config.duplicate` | |
| An option without a default that is not given | `config.missing` | |
| A value of another type | `value.expected_*` | `field` |
| A number outside the limits | `config.out_of_range` | `min`, `max` |
| A text that is not one of the choices | `config.not_allowed` | `allowed` |

Once every file reads, each element is also checked against the limits of its board
(`primum_core.board_limits`, [board profiles](board-profiles.md)): a number the board does not
take is `config.out_of_board_range` (`element`, `option`, `board`, `min`, `max`), at the value,
or at the element when the value is its driver's default. And a number must be limited by
someone: an option that neither its driver nor the board of the element limits is
`config.unlimited` (`element`, `option`, `board`), whatever its value.

**The action of a clip** (`.sec`, `tracks[].clips[]`: `action` and `arguments`, a list of
`name` and `value`), once every file reads (`primum_core.actions`); `action` and `element` in
every case:

| Problem | Code | Also |
|---|---|---|
| A track on an element that takes no actions (an input) | `track.element_without_actions` | `element` only |
| A track on an element whose type has no driver yet (`i2c_device`) | `track.element_without_driver` | `element` and `type` only |
| An action the element's driver does not have | `action.unknown` | `available` |
| An argument for a parameter the action does not have | `action.param_unknown` | `parameter` |
| An argument given twice | `action.param_duplicate` | `parameter` |
| A parameter without a default that gets no argument | `action.param_missing` | `parameter` |
| A value of another type | `value.expected_*` | `field` |
| A number outside the limits | `action.param_out_of_range` | `parameter`, `min`, `max` |
| A text that is not one of the choices | `action.param_not_allowed` | `parameter`, `allowed` |

A track of a component plays a parameter, whose type is not known until a block gives it an
element. Its clips are checked there and reported at the block, once per different problem
however many clips have it. A component nothing includes is not checked, and neither is a
track of it that has no clips (it asks for nothing: given an input, it is reported with its
first clip). A parameter handed on
to an inner component is checked where it finally gets an element.

**The state a clip leaves its element in** (`primum_core.states`), a warning:

| Problem | Code | Params |
|---|---|---|
| A clip that moves its element to rest (a `fade` to 0) and, when it ends, gives it back to an earlier instant command that asks for more (a standing `on`) | `clip.returns_to_instant` | `element`, `action`, `standing` (the action that comes back) |

It is the trap of decision 0017: a clip gives its element back when it ends, so a light faded
out under a standing `on` jumps back on. An instant `off` (or `set` to 0) right where the
fade ends keeps it off. Not reported: a clip whose action holds one state (`off` for two
seconds over a standing `on` is how a light blinks off), a fade that ends elsewhere than at
rest (or that starts there too: a fade from 0 to 0 moves nothing), one followed at its end
by another clip or instant command of the element, one with an instant command inside it
(that one cuts the fade from its instant on: another matter, not reported), one with
nothing standing (the element goes to rest anyway) and one that ends a sequence that holds.
A component's clip is checked at the block that gives it its element. The same states spare
`clip.instant_at_end`: a sequence may end with any instant command that leaves its element at
rest, an `off` or a `set` to 0.

## On a board (the runtime)

`primum_runtime.drivers` implements each manifest on the HAL (decision 0019). A driver is
made from its element (`ElementConfig`: name, type, pin, `active_low`, options), the manifest
of its type and the limits of its board (`create_driver`); a type without an implementation
is `element.type_unsupported` (`element`, `type`).

**Values**, the options of an element and the arguments of an action, are checked again
(`element` and `name` in every case), before anything is claimed or written:

| Problem | Code | Also |
|---|---|---|
| A name the manifest does not declare | `element.value_unknown` | |
| One without a default that is not given | `element.value_missing` | |
| A value of another type, or not among the choices | `element.value_invalid` | |
| A number outside the manifest's limits, or the board's | `element.value_out_of_range` | `min`, `max` |

**An output** (`digital_output`, `pwm_output`) is commanded with the actions of its manifest
(`element.action_unknown` otherwise, with `action` and `available`). A command is instant: the
element goes to the level the action ends in and is read back, and a level that does not
read back is `element.level_not_reached` (`element`, `level`, `read`). A digital output is on
at any level above 0, and only on and off are told apart; a PWM output reads back within one
step of its period (sysfs holds the duty cycle in whole nanoseconds: a third reads back as
0.333333 at 1 kHz). Its safe state is the action the manifest names; a test ties it to the
HAL's own.

**An input** (`digital_input`) hands the HAL its pull, its debounce time and its `active_low`,
all of them: the HAL has no defaults. Its state is the one read when it is claimed, then the
one each event carries: two events of the same kind in a row (a pulse too short for the
kernel to tell its edges apart) do not flip it. Events carry the sequence number of their
line; a gap means the kernel dropped some (it keeps 1024 unread), which the driver counts and
logs. The state is still right.

The HAL also refuses a PWM frequency outside what the board takes
(`hal.pwm_frequency_invalid`, with `min_hz` and `max_hz`), from the limit of the profile.

## Adding a driver

Add its manifest to `drivers/`, named after the element type, and run `uv run just gen` (the
CLI and the runtime ship copies). Then its implementation in `primum_runtime.drivers` (a
class with what it asks of the HAL and how it writes and reads a level, and its entry in
`DRIVERS`), its limits enforced on the board and its tests against the simulated HAL
(`CLAUDE.md`: no driver without them). A test checks that every shipped manifest has an
implementation and every implementation a manifest.
