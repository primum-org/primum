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
  type in `drivers/` (`schemas/driver.schema.json`), with the
  actions a clip may ask with their parameters, the options an element takes in a `.hw` file
  (its `config`), its safe state and its conflict policy. `core` gets them from the caller and
  checks every clip and every element against them. A new driver is a new manifest and no
  change to the format of sequences. It is not yet only a manifest: the element types are
  still a closed list in the hardware schema, and `core` knows how each one is wired (a pin,
  a bus and an address); a manifest that also declares its wiring would open that list.
- **A clip holds its action while it lasts.** From `atMs`, for `durationMs`, its sequence
  commands the element with that action. When the clip ends, the element returns to what was
  there under it (the rule is two points below). Nothing a clip does outlives its sequence.
- **A clip of 0 ms is an instant command that stands**: the element takes the state the action
  ends in (a fade, its `to`) and that state stays as the element's background in its own
  sequence, the one it is written in, until the next instant command of that element there or
  until that sequence ends. A clip with a length plays over it and gives the element back to
  it: `on` at 0 s and `set(30)` from 5 to 6 s is a light that is on, dims for a second and is
  on again. To leave it somewhere else after a clip, put an instant command where the clip
  ends (a `fade` to 0 and an instant `off`).
- **A sequence does the same included as started on its own.** An instant command inside a
  component stands until the component ends, that is, until the block that includes it ends,
  never for the rest of the sequence that includes it: a component that flashes a light for
  half a second does so wherever it is placed.
- **One rule says who commands an element.** A command is in force while it lasts: a clip for
  its length, an instant command until the next one of that element in its own sequence or
  the end of that sequence (of the block, when it is included). Of the sequences with a command in force on an element, those of the
  highest priority count (decision 0006), and among their commands the one that started last
  wins, whichever sequence it is from. With nothing in force, the element is in its safe
  state. So when a clip ends the element goes to the latest command still in force on that
  priority (the standing command of its own sequence, or a clip or a standing command of
  another sequence that started after it), else to what a lower priority says, else to its
  safe state.
- **A sequence ends when its last clip ends**; an instant clip ends where it starts. An instant
  clip that is the last thing of its sequence therefore shows nothing: the sequence is over.
- **An instant clip takes its instant**: no other clip of its element may start in that same
  millisecond, nor may it fall inside another clip of the element (`track.clips_overlap`).
  *Provisional*: it is stricter than a standing command needs, since an instant command and a
  clip with a length do not compete. Today an instant `on` and a clip that start together
  overlap, and so does the instant `off` where a `fade` ends if another clip starts there.
  Block 3.2b relaxes it, which breaks no project.
- **The safe state of a driver is one of its actions** that needs no arguments (`off`): where
  the element rests when nothing commands it, on stop and on panic.
- **Arguments and options are values given by name**, written in the file. A clip that takes the
  value of a component's parameter or of a variable comes with the compiler (phase 4).
- **Levels are percentages**, 0 to 100, as people say them; the HAL's 0 to 1 is the driver's
  business.
- **The first actions**: a digital output goes `on` and `off`; a PWM output goes `on`, `off`,
  `set` to a `level` and `fade`s `from` a level `to` another over the clip. A digital input has
  no actions: a track on one is an error (`track.element_without_actions`); it is listened to,
  with an event. A type without a driver yet takes no track either, with its own code
  (`track.element_without_driver`): the advice for an input does not fit it.
- **Two sequences that may run at once on an element of an exclusive driver are an error**
  (`sequence.exclusive_element_shared`), not the warning it is on the others: one sequence owns
  such an element while it runs (motors, servos; decision 0006).

## Alternatives considered
- **A clip as a command that stays** (`on` leaves the relay on until an `off`): stopping a
  sequence halfway would leave elements wherever they were, and the timeline would not show
  what is on at each moment.
- **An instant command that lasts only until the next clip** of its element, whatever its
  length: after `on` at 0 s and `set(30)` from 5 to 6 s the light would be off from 6 s, which
  is not what whoever writes it expects, and `core` could not warn about it without knowing
  where each action leaves its element. With a standing command the rule is one: when a clip
  ends, the element goes back to what was under it.
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
- A manifest holds what is true of an element type on every platform. Two limits in the first
  manifests are not that: the PWM frequency and the debounce time are what building the HAL
  showed on one Raspberry Pi 4. They stay as provisional values until block 3.3 moves them to
  the board profile, sourced from the manufacturer's documentation, where `core` checks each
  element against the profile of its board and the drivers enforce them again.
- A component is checked where a block gives its parameter an element: only there is the
  element's type known.
- These rules are prose until something runs them: block 3.2b turns "who commands an element
  at an instant" into a pure function of `core` with its tests, before the engine. What it
  finds wrong here is corrected there.
- The engine (phase 4) implements exactly this: hold, give back to the standing command, the
  layer below or the safe state, and instant commands that stand until the next one or the end.
- A `fade` to 0 that is not the last thing of its sequence gives the element back to a
  standing `on`: it needs an instant `off` where it ends. `core` does not warn about it: it
  does not know where an action leaves its element.
- The names of actions, parameters and options are identifiers; what people read in the UI
  comes from the catalogs (phase 5).
