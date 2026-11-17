# 0018. A board limits options in its profile; an action declares the state it ends in

- Status: Accepted
- Date: 2026-11-17

## Context
The first manifests (decision 0016) carried two limits that were not theirs: a PWM frequency
of 1 Hz to 100 kHz and a debounce time of 0 to 10 s, which is what building the HAL showed on
one Raspberry Pi 4. A manifest is for every platform; what a board can do differs from board
to board and is written in its manufacturer's documentation.

And `core` knew the name of an action, not what it does. It spared an instant `off` at the end
of a sequence by its name (an instant `set` to 0 was reported), and it could not warn about
the trap decision 0017 left: a `fade` to 0 under a standing `on` ends with the light jumping
back on.

## Decision
- **What a board can do is data of its profile**: a list of `limits`, each the element type
  and the option it limits, a minimum and a maximum, and the `sources` it comes from (the
  manufacturer's documentation, or the source of the system Primum ships), with a `note` on
  how it follows from them. A limit without a source is refused. `core` checks each element
  against the limits of its board, generically: no code per driver, and a new board is only
  data.
- **A manifest keeps the option, its type, its default, and the limits Primum itself sets**
  on every board. The debounce time is one: no board limits it (the kernel takes 32 bits of
  microseconds and a Raspberry Pi debounces in software), so 0 to 10 s stays in the manifest.
- **`rpi4b` takes a PWM frequency of 1 Hz to 100 kHz**, read in the kernel branch the
  development board runs (`rpi-6.18.y`); the profile is read again for the kernel Primum OS
  ships. Its controller would go from 0.012 Hz
  to 25 MHz (a 50 MHz clock, a period of 2 to 2^32 cycles). The minimum is the lowest whole
  number of hertz. The maximum is a choice of resolution: 100 kHz leaves 500 steps of level.
- **An action declares the state it leaves its element in**, its `endState`: a level from 0 to
  100, fixed or given by one of its parameters. An action that moves its element over its
  clip also declares its `startState`. A driver needs the first anyway to carry out an
  instant command.
- With it `core` compares states, not names: a sequence may end with any instant command that
  leaves its element at rest, and a clip that moves its element to rest and then gives it
  back to an earlier instant command that asks for more is a warning
  (`clip.returns_to_instant`). Earlier: placed no later than the clip starts. One placed
  inside the clip cuts it from its instant on, so the clip never reaches rest and nothing
  comes back: another mistake, with another cure, and not reported.

## Alternatives considered
- **Physical data in the profile** (the clock, the range of the period) with `core` deriving
  the limits: closer to the sources, but `core` would need code for each kind of driver, and
  the choice of resolution would still have to live somewhere. The numbers are in the `note`.
- **The controller's own maximum, 25 MHz**: true to the board and useless to a person, whose
  fade would move in two steps.
- **The debounce time in the profile too**: one place for every limit, but for `rpi4b` it
  would cite no source, since no source limits it.
- **A state of any type** (a text for a motor's direction): nothing needs it yet. A level is
  what the three drivers have; the field can widen without breaking them.
- **Warning about every clip that ends in another state than the one that comes back**: a
  clip that holds `off` for two seconds over a standing `on` is how a light blinks off, and a
  fade to 30 that returns to 100 may be meant. Only moving to rest and coming back on is
  almost never meant.

## Consequences
- A project with a PWM frequency its board does not take gets `config.out_of_board_range`,
  naming the board; the same project on another board may be valid.
- The limits of `rpi4b` are arithmetic on its sources, not a measure: the `hw` test at both
  ends comes with the PWM driver (block 3.3b).
- A profile that says nothing about an option leaves it with its driver's limits only: a new
  board with PWM must not forget its frequency. Nothing checks that yet.
- The warning is given where a clip's element is known and looks at one sequence: a fade in
  an included sequence under a standing `on` of the sequence that includes it is not reported
  when the included sequence names the element itself, not through a parameter.
- The engine (phase 4) can hold a clip "as it ended" from the same `endState`.
