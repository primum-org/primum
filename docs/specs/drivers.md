# Drivers

A driver implements an element type on a platform. What it offers is described by a
**manifest**: data that `core` reads to check a project without hardware, and that the UI will
read to show what each element can do. One file per element type in `drivers/`
(`drivers/pwm_output.json`), named after the type. Format: `schemas/driver.schema.json`.
The implementations live in the runtimes (block 3.3). Why: decision 0016.

## Contents

| Field | Meaning |
|---|---|
| `id`, `kind` (`driver`), `schemaVersion` (1) | As every file format |
| `elementType` | The type of the elements it serves, as `.hw` files write it (`pwm_output`): the file name |
| `capabilities` | What the element can do in general terms: `switch`, `level`, `color`, `position`, `measure` |
| `platforms` | The runtimes that implement it: `linux`, `esp32`, `rp2040`, `avr` |
| `actions` | What a clip may ask of the element, each with a `name` and its `parameters`. None for an element that only reads |
| `config` | The options an element of this type takes in a `.hw` file, beyond its wiring |
| `safeState` | The action the element rests in when nothing commands it, on stop and on panic |
| `conflictPolicy` | `latest_wins` (lights, relays) or `exclusive` (motors, servos: one sequence owns the element while it runs) |

A parameter of an action and an option of the configuration are written the same way:

| Field | Meaning |
|---|---|
| `name` | How clips and elements name it (`level`, `frequencyHz`): a lowercase letter, then letters and digits |
| `type` | `number`, `integer`, `boolean` or `text` |
| `min`, `max` | Its limits (numbers only, both or neither) |
| `choices` | The values it allows (texts only) |
| `default` | The value it takes when not given. Without one it must be given |

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
- a driver with actions has a `safeState` and a `conflictPolicy` (`schema.missing_field`), and
  the safe state is one of its actions that needs no arguments (`driver.unknown_safe_state`); a
  driver without actions has neither (`schema.unexpected_field`).

The manifests ship with Primum and its tests read them, so a broken one is a bug, not a
problem of a project.

## The drivers of this version

| Type | Capabilities | Actions | Options (default) | Safe state | Conflicts |
|---|---|---|---|---|---|
| `digital_output` | switch | `on`, `off` | | `off` | latest wins |
| `pwm_output` | switch, level | `on`, `off`, `set(level)`, `fade(from, to)` | `frequencyHz` 1–100000 (1000) | `off` | latest wins |
| `digital_input` | measure | none | `pull` `up`, `down` or `none` (`up`); `debounceMs` 0–10000 (20) | | |

- A `level`, and the `from` and `to` of a fade, are percentages: 0 to 100, decimals allowed.
- On a PWM output `on` is the level 100 and `off` the level 0; on a digital output they are
  its two states (which electrical level is "on" is the element's `activeLow`).
- `fade` goes from one level to the other over the length of its clip; as an instant clip it
  jumps to `to`.
- The limits of `frequencyHz` and `debounceMs` are provisional: they are what building the HAL
  showed on one Raspberry Pi 4, not something of the element type. A manifest holds what is
  true on every platform (that the option exists, its type, its default); what a board's PWM
  and inputs can do is data of its [board profile](board-profiles.md), taken from the
  manufacturer's documentation. Block 3.3 moves these limits there and checks each element
  against the profile of its board.
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
however many clips have it. A component nothing includes is not checked. A parameter handed on
to an inner component is checked where it finally gets an element.

## Adding a driver

Add its manifest to `drivers/`, named after the element type, and run `uv run just gen` (the
CLI ships a copy). Its implementation, its limits enforced on the board and its test against
the simulated HAL come with it (`CLAUDE.md`: no driver without them).
