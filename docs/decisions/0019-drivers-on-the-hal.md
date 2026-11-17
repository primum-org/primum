# 0019. Drivers implement manifests on the HAL; commands are instant and read back

- Status: Accepted
- Date: 2026-11-17

## Context
The runtime drove one digital output straight through the HAL. The manifests of block 3.2
described three element types as data, the board profile had gained the limits of its
elements' options (decision 0018), and nothing in the runtime used either. The HAL had
defaults of its own that disagreed with the manifests (a pull of `up` where the manifest has
none, a debounce of 0 where it says 20).

Two things constrained the design. After a `kill -9` a PWM channel stays at its last level
until the safe-state unit of block 3.4 covers PWM. And the API runs on one thread, the event
loop's, so nothing may block it or need a lock.

## Decision
- **A driver is made from three things**: the element (name, wiring, options), the manifest
  of its type and the limits of its board. It resolves its options when it is made (the
  manifest's default for one not given), so a wrong option fails before anything is claimed.
  It says what it needs of the HAL (`spec`, with every option: the HAL's specs have no
  defaults) and takes its element from the HAL once claimed (`bind`).
- **A command is an action of the manifest, carried out as an instant command**: the element
  goes to the state the action ends in (`endState`, decision 0018) and is read back. A level
  that does not read back is an error (`element.level_not_reached`): for a digital output, on
  or off; for a PWM output, within one step of its period. The output then reports the
  level it read, and listeners are told: the state never shows what was only asked. Moving an element over time (a
  `fade` with a length) is the engine's (phase 4), on top of this.
- **Limits are enforced three times**, each by who can: `core` on the project, the driver on
  what reaches it (the manifest's limits and the board's), and the HAL on what it can express
  at all (the PWM frequency its board takes). The driver fails closed as `core` does: a
  number that neither its manifest nor its board limits is refused
  (`element.value_unlimited`), since the service's own options never pass through `core`. The runtime's errors for values are
  `element.*`; `driver.*` stays for problems of a manifest.
- **The `Controller` owns the drivers**: it makes them, claims everything at once
  (decision 0015) and keeps outputs by name. Panic stays the HAL's safe state, read back,
  not the manifest's action: safety does not depend on a manifest being right. A test per
  output driver ties the two.
- **Inputs are listened to through a descriptor.** The HAL gives one that is readable while
  events wait; the event loop watches it and the controller reads the events then. No
  thread, no polling. The state of an input is taken from each event, never toggled, and a
  gap in the events' sequence numbers is counted and logged.
- **The service does not offer PWM until block 3.4.** The drivers and the controller handle
  PWM outputs; the service's options cannot ask for one. Its state gains `inputs`
  (`{"name", "active"}`) next to the `outputs` of decision 0011.

## Alternatives considered
- **Drivers as plain functions over the HAL's objects**: less code, but the options, the
  limits and the read-back would be repeated by each caller.
- **Validating in `core` only**: the runtime will receive a validated package, but a driver
  is the last thing between a value and the hardware, and the service's own options never
  pass through `core`.
- **A thread that waits for input events**: simple, and it would put the controller on two
  threads.
- **Offering PWM now**, or merging this block with 3.4: the first opens the `kill -9` gap to
  anyone with the page; the second makes one block of two.
- **Panic through each driver's safe-state action**: one mechanism less, but a wrong
  manifest would then be a wrong panic.

## Consequences
- A new driver is a manifest, a class with `spec`, `bind` and how it writes and reads a
  level, an entry in `DRIVERS` and its tests against the simulated HAL.
- The simulated HAL has a pipe when inputs are claimed, so the same watch is tested without
  hardware; it can produce two equal events and lost ones.
- The `hw` tests of this block were written without the board and are to be run on it.
- A state is a level: a driver whose elements have another kind of state (a motor's
  direction) needs decision 0018 widened first.
