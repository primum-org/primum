# 0025. The service runs a package, checked against its drivers; elements are asked for by id

- Status: Accepted
- Date: 2026-11-21

## Context
Since phase 1 the service was told its elements by options of its own: one LED (`--pin`),
maybe one button and one dimmer, each with a fixed name the API used (`PUT
/api/outputs/led`). A deployment package (decision 0024) says the elements of a project, and
`core` reads one and checks that it holds together, but not that a board can run it: only the
runtime has the drivers and the profile of its board.

## Decision
- **The service takes a package** (`--package`, `PRIMUM_PACKAGE`): its elements and its board
  are the package's. The options of elements stay, for one thing or the other, never both,
  until packages are activated on the board (block 4.5): the development Pi goes on as it is.
- **A package is checked whole before anything is claimed**, and one that fails is refused
  and the service does not start: `core`'s reading (shape, hash, that it holds together),
  then, with the runtime's own manifests and profile, that its board has a profile, every
  element a driver that takes its options, and every command an action its driver has with
  arguments it takes. An argument read from a variable is checked by the variable's type and
  limits, as `core` checks a project's. The wiring is checked by `core`'s own rules for a
  project (a pin the board lacks or reserves, two elements on one pin, PWM where there is
  none): the HAL refuses some of that at the claim, by the pin alone, and knows nothing of
  reserved pins, so it is the last word and not the check.
- **An element is asked for by its id**, not its name: `PUT /api/outputs/{id}`, and the state
  gives each output and input its `id` and its `name`. A name is for people: it may change,
  be shared, or have spaces. An element told of by an option has no id and goes by its name
  (`led`, `button`, `dimmer`), so nothing changes there.
- **Nothing runs yet.** The service drives the elements of the package as it drove its own:
  by commands of the API, test mode, panic. Its sequences are the engine's (block 4.3b).

## Alternatives considered
- **A package only, the options gone**: one way to say what there is, but provisioning and
  the `just pi-*` tasks would have to build and copy a package, untried on the board.
- **Elements by name**: no change to the page, and a package would need unique names with
  nothing odd in them.
- **Starting with the elements that pass and leaving the rest out**: a show with half its
  lights, and nobody told why.

## Consequences
- A package for another board, or built by a version with other drivers, is refused at the
  start with what is wrong, not half way through a show.
- A service that cannot run its package does not start, so the page cannot say why: only the
  journal does, and systemd goes on restarting it. Activation (4.5) checks a package before
  it replaces the one that runs, and gives "cannot run this" an exit status that is not
  restarted.
- An error about an element of a package says its name, for people, and its id, since two
  elements may share a name. `output.unknown` says the id that was asked for.
- Not checked yet: that an event's element is an input. Events come with 4.4.
