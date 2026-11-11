# 0016. A clip holds its action while it lasts; drivers declare what an element can be asked

- Status: Accepted
- Date: 2026-11-11

## Context
A clip named its action with any word: nothing said which actions an element has, with which
values, or what the element does when the clip ends. A clip of 0 ms was accepted and ignored.
Drivers arrive in phase 3 and each needs a declared safe state, limits and conflict policy
(`CLAUDE.md`), which `core` must know to validate a project without hardware.

## Decision
- **Drivers are described by manifests**, data like the board profiles: one file per element
  type in `drivers/` (`schemas/driver.schema.json`), with its capabilities, platforms, the
  actions a clip may ask with their parameters, the options an element takes in a `.hw` file
  (its `config`), its safe state and its conflict policy. `core` gets them from the caller and
  checks every clip and every element against them. A new driver is a new manifest, not a
  change of the formats.
- **A clip holds its action while it lasts.** From `atMs`, for `durationMs`, its sequence
  commands the element with that action. When the clip ends the sequence stops commanding the
  element: it returns to what a sequence on a lower priority says (decision 0006) or, if none
  does, to its safe state. Nothing a clip does outlives its sequence.
- **A clip of 0 ms is an instant command whose effect stays**: the element takes the state the
  action ends in (a fade, its `to`) and keeps it until the next clip of that element starts, or
  until the sequence ends. Sequences are read flattened (`workspace.md`), so "next clip" and
  "ends" are those of the sequence that runs, not of a component inside it.
- **A sequence ends when its last clip ends**; an instant clip ends where it starts. An instant
  clip that is the last thing of its sequence therefore shows nothing: the sequence is over.
- **An instant clip takes its instant**: no other clip of its element may start in that same
  millisecond, nor may it fall inside another clip of the element (`track.clips_overlap`).
- **The safe state of a driver is one of its actions** that needs no arguments (`off`): where
  the element rests when nothing commands it, on stop and on panic.
- **Arguments and options are values given by name**, written in the file. A clip that takes the
  value of a component's parameter or of a variable comes with the compiler (phase 4).
- **Levels are percentages**, 0 to 100, as people say them; the HAL's 0 to 1 is the driver's
  business.
- **The first actions**: a digital output goes `on` and `off`; a PWM output goes `on`, `off`,
  `set` to a `level` and `fade`s `from` a level `to` another over the clip. A digital input has
  no actions: a track on one is an error (`track.element_without_actions`); it is listened to,
  with an event.
- **Two sequences that may run at once on an element of an exclusive driver are an error**
  (`sequence.exclusive_element_shared`), not the warning it is on the others: one sequence owns
  such an element while it runs (motors, servos; decision 0006).

## Alternatives considered
- **A clip as a command that stays** (`on` leaves the relay on until an `off`): stopping a
  sequence halfway would leave elements wherever they were, and the timeline would not show
  what is on at each moment.
- **Refusing clips of 0 ms** until a driver declares actions that are instant by nature (a
  servo's move, a sound): simpler, but "turn it on and leave it on for the rest of the sequence"
  would need its duration worked out by hand and kept in step with every edit.
- **The actions of each type in the sequence schema**: every new driver would change a file
  format, and the limits of each parameter would live in two places.
- **Shortcuts** (`fade_in`, `fade_out`, `blink`): one way to say each thing for now; they can
  be added to a manifest later without touching the formats.

## Consequences
- `primum validate` reports an action its element cannot do, an argument or an option that is
  missing, unknown or outside its limits, before anything reaches a board.
- The limits found while building the HAL (the PWM frequency, the debounce time) are data in the
  manifests; the drivers of block 3.3 enforce them again on the board.
- A component is checked where a block gives its parameter an element: only there is the
  element's type known.
- The engine (phase 4) implements exactly this: hold, release to the layer below or the safe
  state, and instant commands that last until the next clip or the end.
- The names of actions, parameters and options are identifiers; what people read in the UI
  comes from the catalogs (phase 5).
